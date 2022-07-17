import dataclasses
from typing import Any, Callable, Dict, Optional, Type, Union

import pydantic
from pydantic import validate_model
from pydantic.fields import Field, FieldInfo, Required, Undefined
from pydantic.typing import NoArgAnyCallable

from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper
from strawberry_sqlalchemy_mapper.mapper import _GENERATED_FIELD_KEYS_KEY, BaseModelType


class PostponedValidationMixin:
    """Postpone model validation.

    This mixin allow to instantiate model with invalid data
    and to validate it later using the `check()` method

    >>> user = User(id=1, username="foo")
    >>> user.check()
    """

    def __new__(cls, *args, **kwargs) -> pydantic.BaseModel:
        if not args and not kwargs:
            return super().__new__(cls)
        return cls.construct(*args, **kwargs)

    def __init__(self, *_, **__) -> None:
        pass

    def check(self) -> None:
        """Validate data against the model.

        Raises:
            `ValidationError` if data is not valid
        """
        values, fields_set, validation_error = validate_model(
            self.__class__, self.__dict__
        )
        if validation_error:
            raise validation_error
        try:
            object.__setattr__(self, "__dict__", values)
        except TypeError as e:
            raise TypeError(
                "Model values must be a dict; you may not have returned "
                + "a dictionary from a root validator"
            ) from e
        object.__setattr__(self, "__fields_set__", fields_set)


class PydanticSQLAMapper(StrawberrySQLAlchemyMapper):
    """Convert generated strawberry input types to pydantic model."""

    def __init__(self, *args, postponed_validation: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.postponed_evaluation = postponed_validation

    def _field_definitions(self, type_):
        """Generate field definitions suitable to pass to pydantic.create_model()."""

        field_definitions: Dict[str, Any] = {}

        for field in dataclasses.fields(type_):
            default: Any = Undefined
            default_factory: Optional["NoArgAnyCallable"] = None
            field_info: FieldInfo

            type_origin = getattr(field.type, "__origin__", None)
            type_args = getattr(field.type, "__args__", [])

            if field.default is not dataclasses.MISSING:
                default = field.default
            elif field.default_factory is not dataclasses.MISSING:
                default_factory = field.default_factory
            # Check if field type is Optional
            elif type_origin is not Union and None.__class__ not in type_args:
                default = Required

            if isinstance(default, FieldInfo):
                field_info = default
            else:
                field_info = Field(
                    default=default, default_factory=default_factory, **field.metadata
                )

            field_definitions[field.name] = (
                type_.__annotations__[field.name],
                field_info,
            )

        return field_definitions

    def _to_pydantic_model(
        self,
        pyd_model: Type[pydantic.BaseModel],
        type_: Any,
        sqla_model: Type[BaseModelType],
    ) -> Type[pydantic.BaseModel]:
        """Create a pydantic model from a strawberry input type."""

        if self.postponed_evaluation:
            bases = (*self.input_bases, PostponedValidationMixin, pyd_model)
        else:
            bases = (*self.input_bases, pyd_model)

        pyd_model = pydantic.create_model(
            pyd_model.__name__,
            __base__=bases,
            __module__=pyd_model.__module__,
            **self._field_definitions(type_),
        )

        pyd_model._type_definition = type_._type_definition
        setattr(
            pyd_model,
            _GENERATED_FIELD_KEYS_KEY,
            getattr(type_, _GENERATED_FIELD_KEYS_KEY),
        )

        # Update mapping
        self.input_types[type_.__name__] = pyd_model
        sqla_model = self.input_model_map.pop(type_)
        self.input_model_map[pyd_model] = sqla_model

        return pyd_model

    @classmethod
    def _copy_type(cls, input_class: Any) -> type:
        return type(
            input_class.__name__,
            (),
            {
                "__annotations__": getattr(input_class, "__annotations__", {}),
                "__exclude__": getattr(input_class, "__exclude__", {}),
            },
        )

    def _wrapper(
        self, fn_name: str, model: Type[BaseModelType], *args, **kwargs
    ) -> Callable[[Any], Any]:
        """Wrap `fn_name` decorator to convert generated type to a pydantic model."""
        super_fn = getattr(super(), fn_name)(model, *args, **kwargs)
        to_pydantic_model = self._to_pydantic_model

        def convert(type_: Any):
            if not issubclass(type_, pydantic.BaseModel):
                return super_fn(type_)
            # It's necessary to create a new type to
            # to prevent unwanted mutations from strawberry on the pydantic model
            type_copy = PydanticSQLAMapper._copy_type(type_)
            return to_pydantic_model(type_, super_fn(type_copy), model)

        return convert

    def type(
        self, model: Type[BaseModelType], make_interface=False
    ) -> Callable[
        [Type[object]], Type[Union[pydantic.BaseModel, PostponedValidationMixin]]
    ]:
        return self._wrapper("type", model, make_interface=make_interface)

    def input(
        self, model: Type[BaseModelType], optional=False
    ) -> Callable[[type], Type[Union[pydantic.BaseModel, PostponedValidationMixin]]]:
        return self._wrapper("input", model, optional=optional)

    def finalize(self) -> None:
        # Update model forward refs
        super().finalize()
        for input_ in self.input_types.values():
            input_.update_forward_refs(**self.input_types)
