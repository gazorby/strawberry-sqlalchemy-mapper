from typing import Any, Callable, Type, Union

import pydantic
from pydantic import validate_model

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


class PydanticMapper(StrawberrySQLAlchemyMapper):
    """Convert strawberry input types to pydantic model."""

    def _to_pydantic_model(
        self,
        pyd_model: Type[pydantic.BaseModel],
        input_cls: Any,
        sqla_model: Type[BaseModelType],
    ) -> Type[pydantic.BaseModel]:
        """Create a pydantic model from a strawberry input type."""

        fields_def = {
            f_name: (f_type, getattr(input_cls, f_name, ...))
            for f_name, f_type in input_cls.__annotations__.items()
        }

        pyd_model = pydantic.create_model(
            pyd_model.__name__,
            __base__=(*self.input_bases, PostponedValidationMixin, pyd_model),
            __module__=pyd_model.__module__,
            **fields_def,
        )

        pyd_model._type_definition = input_cls._type_definition
        pyd_model._model = sqla_model
        setattr(
            pyd_model,
            _GENERATED_FIELD_KEYS_KEY,
            getattr(input_cls, _GENERATED_FIELD_KEYS_KEY),
        )

        # Update mapping
        self.input_types[input_cls.__name__] = pyd_model
        sqla_model = self.input_model_map.pop(input_cls)
        self.input_model_map[pyd_model] = sqla_model

        return pyd_model

    @classmethod
    def _copy_input_cls(cls, input_class: Any) -> type:
        return type(
            input_class.__name__,
            (),
            {
                "__annotations__": getattr(input_class, "__annotations__", {}),
                "__exclude__": getattr(input_class, "__exclude__", {}),
            },
        )

    def update_input(
        self, model: Type[BaseModelType]
    ) -> Callable[[type], Type[Union[pydantic.BaseModel, PostponedValidationMixin]]]:
        super_update = super().update_input(model)
        fn = self._to_pydantic_model

        def convert(type_: Any):
            type_copy = PydanticMapper._copy_input_cls(type_)
            return fn(type_, super_update(type_copy), model)

        return convert

    def create_input(
        self, model: Type[BaseModelType]
    ) -> Callable[[type], Type[Union[pydantic.BaseModel, PostponedValidationMixin]]]:
        super_create = super().create_input(model)
        fn = self._to_pydantic_model

        def convert(type_: Any):
            type_copy = PydanticMapper._copy_input_cls(type_)
            return fn(type_, super_create(type_copy), model)

        return convert

    def finalize(self) -> None:
        # Update model forward refs
        super().finalize()
        for input_ in self.input_types.values():
            input_.update_forward_refs(**self.input_types)
