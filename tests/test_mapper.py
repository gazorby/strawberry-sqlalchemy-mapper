import enum
from typing import List, Optional
import datetime
from models import create_employee_and_department_tables, create_employee_table
from sqlalchemy import Column, Enum, Integer, String, Interval, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql.array import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from strawberry.type import StrawberryOptional, StrawberryList

from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper


def _create_polymorphic_employee_table():
    # todo: use pytest fixtures
    Base = declarative_base()

    class Employee(Base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        type = Column(String(50))

        __mapper_args__ = {"polymorphic_identity": "employee", "polymorphic_on": type}

    return Employee


def test_mapper_default_model_to_type_name():
    Employee = create_employee_table()
    assert (
        StrawberrySQLAlchemyMapper._default_model_to_type_name(Employee) == "Employee"
    )


def test_default_model_to_interface_name():
    Employee = create_employee_table()
    assert (
        StrawberrySQLAlchemyMapper._default_model_to_interface_name(Employee)
        == "EmployeeInterface"
    )


def test_model_is_interface_fails():
    Employee = create_employee_table()
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    assert strawberry_sqlalchemy_mapper.model_is_interface(Employee) is False


def test_model_is_interface_succeeds():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    Employee = _create_polymorphic_employee_table()
    assert strawberry_sqlalchemy_mapper.model_is_interface(Employee) is True


def test_is_model_polymorphic():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    Employee = _create_polymorphic_employee_table()
    assert strawberry_sqlalchemy_mapper._is_model_polymorphic(Employee) is True


def test_edge_type_for():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    employee_edge_class = strawberry_sqlalchemy_mapper._edge_type_for("Employee")
    assert employee_edge_class.__name__ == "EmployeeEdge"
    assert employee_edge_class._generated_field_keys == ["node"]


def test_connection_type_for():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    employee_connection_class = strawberry_sqlalchemy_mapper._connection_type_for(
        "Employee"
    )
    assert employee_connection_class.__name__ == "EmployeeConnection"
    assert employee_connection_class._generated_field_keys == ["edges"]
    assert employee_connection_class._is_generated_connection_type is True


def test_get_polymorphic_base_model():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    Employee = _create_polymorphic_employee_table()

    class Lawyer(Employee):
        pass

    class ParaLegal(Lawyer):
        pass

    assert (
        strawberry_sqlalchemy_mapper._get_polymorphic_base_model(Employee) == Employee
    )
    assert strawberry_sqlalchemy_mapper._get_polymorphic_base_model(Lawyer) == Employee
    assert (
        strawberry_sqlalchemy_mapper._get_polymorphic_base_model(ParaLegal) == Employee
    )


def test_convert_column_to_strawberry_type():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    int_column = Column(Integer, nullable=False)
    assert (
        strawberry_sqlalchemy_mapper._convert_column_to_strawberry_type(int_column)
        == int
    )
    string_column = Column(String, nullable=False)
    assert (
        strawberry_sqlalchemy_mapper._convert_column_to_strawberry_type(string_column)
        == str
    )


def test_convert_array_column_to_strawberry_type():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    column = Column(ARRAY(String))
    assert (
        strawberry_sqlalchemy_mapper._convert_column_to_strawberry_type(column)
        == Optional[List[str]]
    )
    column = Column(ARRAY(String), nullable=False)
    assert (
        strawberry_sqlalchemy_mapper._convert_column_to_strawberry_type(column)
        == List[str]
    )


def test_convert_enum_column_to_strawberry_type():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

    class SampleEnum(enum.Enum):
        one = 1
        two = 2
        three = 3

    column = Column(Enum(SampleEnum))
    assert (
        strawberry_sqlalchemy_mapper._convert_column_to_strawberry_type(column)
        == Optional[SampleEnum]
    )
    column = Column(Enum(SampleEnum), nullable=False)
    assert (
        strawberry_sqlalchemy_mapper._convert_column_to_strawberry_type(column)
        == SampleEnum
    )


def test_convert_relationship_to_strawberry_type():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    _, Department = create_employee_and_department_tables()
    employees_property = Department.employees.property
    assert (
        strawberry_sqlalchemy_mapper._convert_relationship_to_strawberry_type(
            employees_property
        ).__name__
        == "EmployeeConnection"
    )


def test_get_relationship_is_optional():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    _, Department = create_employee_and_department_tables()
    employees_property = Department.employees.property
    assert (
        strawberry_sqlalchemy_mapper._get_relationship_is_optional(employees_property)
        is True
    )


def test_add_annotation():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

    class Base:
        a: int = 3
        b: str = "abc"

    field_keys = []
    key = "name"
    annotation = "base_name"
    strawberry_sqlalchemy_mapper._add_annotation(Base, key, annotation, field_keys)
    assert Base.__annotations__[key] == annotation
    assert field_keys == [key]


def test_connection_resolver_for():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    _, Department = create_employee_and_department_tables()
    employees_property = Department.employees.property
    assert (
        strawberry_sqlalchemy_mapper.connection_resolver_for(employees_property)
        is not None
    )


def test_type_simple():
    Employee = create_employee_table()
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

    @strawberry_sqlalchemy_mapper.type(Employee)
    class Employee:
        pass

    strawberry_sqlalchemy_mapper.finalize()
    additional_types = list(strawberry_sqlalchemy_mapper.mapped_types.values())
    assert len(additional_types) == 1
    mapped_employee_type = additional_types[0]
    assert mapped_employee_type.__name__ == "Employee"
    assert len(mapped_employee_type._type_definition._fields) == 2
    employee_type_fields = mapped_employee_type._type_definition._fields
    name = list(filter(lambda f: f.name == "name", employee_type_fields))[0]
    assert name.type == str
    id = list(filter(lambda f: f.name == "id", employee_type_fields))[0]
    assert id.type == int


def test_type_relationships():
    Employee, _ = create_employee_and_department_tables()
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

    @strawberry_sqlalchemy_mapper.type(Employee)
    class Employee:
        pass

    strawberry_sqlalchemy_mapper.finalize()
    additional_types = list(strawberry_sqlalchemy_mapper.mapped_types.values())
    assert len(additional_types) == 2
    mapped_employee_type = additional_types[0]
    assert mapped_employee_type.__name__ == "Employee"
    assert len(mapped_employee_type._type_definition._fields) == 4
    employee_type_fields = mapped_employee_type._type_definition._fields
    name = list(filter(lambda f: f.name == "department_id", employee_type_fields))[0]
    assert type(name.type) == StrawberryOptional
    id = list(filter(lambda f: f.name == "department", employee_type_fields))[0]
    assert type(id.type) == StrawberryOptional


def test_override_annotation():
    Base = declarative_base()
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

    class A(Base):
        __tablename__ = "a"
        id = Column(Integer, autoincrement=True, primary_key=True)
        interval = Column(Interval)

    @strawberry_sqlalchemy_mapper.type(A)
    class AType:
        interval: datetime.timedelta

    atype_fields = AType._type_definition._fields
    interval = list(filter(lambda f: f.name == "interval", atype_fields))[0]
    assert interval.type == datetime.timedelta


def test_default_arguments_last_input():
    Base = declarative_base()
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

    class User(Base):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    class Child(Base):
        __tablename__ = "child"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("user.id"))
        parent_id = Column(Integer, ForeignKey("parent.id"))

        # default argument
        parent = relationship("Parent", back_populates="children")
        # non-default argument
        user = relationship("User")

    class Parent(Base):
        __tablename__ = "parent"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("user.id"))

        children = relationship("Child", back_populates="parent")
        user = relationship("User")

    @strawberry_sqlalchemy_mapper.input(User)
    class UserCreate:
        pass

    @strawberry_sqlalchemy_mapper.input(Child)
    class ChildCreate:
        pass

    @strawberry_sqlalchemy_mapper.input(Parent)
    class ParentCreate:
        pass

    strawberry_sqlalchemy_mapper.finalize()

    parent_fields = ParentCreate._type_definition._fields
    children = list(filter(lambda f: f.name == "children", parent_fields))[0]
    user = list(filter(lambda f: f.name == "user", parent_fields))[0]

    assert type(children.type) == StrawberryOptional
    assert type(children.type.of_type) == StrawberryList
    assert children.type.of_type.of_type == ChildCreate

    assert type(user.type) == StrawberryOptional
    assert user.type.of_type == UserCreate
