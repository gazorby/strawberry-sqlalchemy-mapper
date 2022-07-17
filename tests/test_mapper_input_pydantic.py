import pytest
import strawberry
from models import create_employee_table
from pydantic import BaseModel, ValidationError

from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper
from strawberry_sqlalchemy_mapper.pydantic import PydanticSQLAMapper


def test_basic():
    Employee = create_employee_table()
    gql_mapper_pydantic = PydanticSQLAMapper(
        model_to_type_name=lambda name: f"{name.__name__}Type",
    )
    gql_mapper = StrawberrySQLAlchemyMapper(
        model_to_type_name=lambda name: f"{name.__name__}Type",
    )

    @gql_mapper.input(Employee)
    class EmployeeCreate:
        pass

    @gql_mapper_pydantic.input(Employee)
    class EmployeeCreateModel(BaseModel):
        pass

    # Assert pydantic model
    assert issubclass(EmployeeCreateModel, BaseModel)
    schema = EmployeeCreateModel.schema()
    assert schema["properties"] == {"name": {"title": "Name", "type": "string"}}

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type(name="Mutation")
    class MutationPydantic:
        @strawberry.field
        def create_employee(input: EmployeeCreateModel) -> None:
            assert input == EmployeeCreateModel(name="foo")

    @strawberry.type
    class Mutation:
        @strawberry.field
        def create_employee(input: EmployeeCreate) -> None:
            assert input == EmployeeCreate(name="foo")

    query = """
        mutation createEmployee {
            createEmployee(input: {name: "foo"})
        }
    """

    expected_schema = """
input EmployeeTypeCreateInput {
  name: String!
}

type Mutation {
  createEmployee(input: EmployeeTypeCreateInput!): Void
}

type Query {
  hello: String!
}

\"\"\"Represents NULL values\"\"\"
scalar Void
"""

    # Assert schema
    schema_pydantic = strawberry.Schema(query=Query, mutation=MutationPydantic)
    schema = strawberry.Schema(query=Query, mutation=Mutation)

    assert (
        schema.as_str().strip()
        == schema_pydantic.as_str().strip()
        == expected_schema.strip()
    )

    result = schema_pydantic.execute_sync(query)
    assert result.errors is None


def test_postponed_evaluation():
    Employee = create_employee_table()
    gql_mapper = PydanticSQLAMapper(
        model_to_type_name=lambda name: f"{name.__name__}Type",
        postponed_validation=True,
    )

    @gql_mapper.input(Employee)
    class EmployeeCreate(BaseModel):
        pass

    # Everything is fine, model is not yet validated
    employee = EmployeeCreate(name=object())

    with pytest.raises(ValidationError):
        employee.check()
