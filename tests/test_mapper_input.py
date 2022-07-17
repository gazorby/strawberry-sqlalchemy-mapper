import strawberry
from models import create_employee_and_department_tables, create_employee_table

from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper


def test_basic_create():
    Employee = create_employee_table()
    gql_mapper = StrawberrySQLAlchemyMapper(
        model_to_type_name=lambda name: f"{name.__name__}Type",
    )

    @gql_mapper.type(Employee)
    class EmployeeType:
        id: strawberry.ID

    @gql_mapper.create_input(Employee)
    class EmployeeCreate:
        pass

    @strawberry.type
    class Query:
        hello: str = "Hello"

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
    schema = strawberry.Schema(query=Query, mutation=Mutation)
    assert schema.as_str().strip() == expected_schema.strip()
    result = schema.execute_sync(query)
    assert result.errors is None


def test_basic_update():
    Employee = create_employee_table()
    gql_mapper = StrawberrySQLAlchemyMapper(
        model_to_type_name=lambda name: f"{name.__name__}Type",
    )

    @gql_mapper.type(Employee)
    class EmployeeType:
        id: strawberry.ID

    @gql_mapper.update_input(Employee)
    class EmployeeUpdate:
        pass

    # @gql_mapper.type(Basic2)
    # class Basic2Type:
    #     id: strawberry.ID

    # @gql_mapper.update_input(Basic2)
    # class Basic2Update:
    #     pass

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def update_employee(input: EmployeeUpdate) -> None:
            assert input == EmployeeUpdate(id="1", name="foo")

    query = """
        mutation updateEmployee {
            updateEmployee(input: {id: 1, name: "foo"})
        }
    """

    expected_schema = """
input EmployeeTypeUpdateInput {
  id: ID!
  name: String = null
}

type Mutation {
  updateEmployee(input: EmployeeTypeUpdateInput!): Void
}

type Query {
  hello: String!
}

\"\"\"Represents NULL values\"\"\"
scalar Void
"""

    # Assert schema
    schema = strawberry.Schema(query=Query, mutation=Mutation)
    assert schema.as_str().strip() == expected_schema.strip()
    result = schema.execute_sync(query)
    assert result.errors is None


def test_list_input():
    Employee, Department = create_employee_and_department_tables()
    gql_mapper = StrawberrySQLAlchemyMapper(
        model_to_type_name=lambda name: f"{name.__name__}Type",
    )

    @gql_mapper.type(Department)
    class DepartmentType:
        id: strawberry.ID

        @gql_mapper.create_input(Department)
        class Create:
            pass

    @gql_mapper.type(Employee)
    class EmployeeType:
        id: strawberry.ID

        @gql_mapper.create_input(Employee)
        class Create:
            __exclude__ = ["department_id", "department"]

    # important to call finalize here
    gql_mapper.finalize()

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def create_department(input: DepartmentType.Create) -> None:
            assert input.name == "foo"
            assert input.employees == [
                EmployeeType.Create(name="hello"),
                EmployeeType.Create(name="world"),
            ]

    query = """
        mutation createDepartment {
            createDepartment(
                input: {
                    name: "foo",
                    employees: [
                        { name: "hello" },
                        { name: "world" }
                    ]
                }
            )
        }
    """
    schema = strawberry.Schema(query=Query, mutation=Mutation)
    result = schema.execute_sync(query)
    assert result.errors is None


def test_create_exclude():
    Employee, _ = create_employee_and_department_tables()

    gql_mapper = StrawberrySQLAlchemyMapper(
        model_to_type_name=lambda name: f"{name.__name__}Type",
    )

    # schema definition
    @gql_mapper.type(Employee)
    class EmployeeType:
        id: strawberry.ID
        __exclude__ = ["department", "department_id"]

    @gql_mapper.create_input(Employee)
    class EmployeeCreate:
        __exclude__ = ["department", "department_id"]

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def create_employee(input: EmployeeCreate) -> EmployeeType:
            return EmployeeType(id=1, name=input.name)

    query = """
        mutation createEmployee {
            createEmployee(input: {name: "foo"}) {
                id
                name
            }
        }
    """

    expected_schema = """
type EmployeeType {
  id: ID!
  name: String!
}

input EmployeeTypeCreateInput {
  name: String!
}

type Mutation {
  createEmployee(input: EmployeeTypeCreateInput!): EmployeeType!
}

type Query {
  hello: String!
}
"""

    # Assert schema
    schema = strawberry.Schema(query=Query, mutation=Mutation)
    assert schema.as_str().strip() == expected_schema.strip()
    # Assert query result
    result = schema.execute_sync(query)
    assert result.data == {"createEmployee": {"id": "1", "name": "foo"}}


def test_update_exclude():
    gql_mapper = StrawberrySQLAlchemyMapper(
        model_to_type_name=lambda name: f"{name.__name__}Type",
    )
    Employee = create_employee_table()

    @gql_mapper.type(Employee)
    class EmployeeType:
        id: strawberry.ID

        __exclude__ = ["children"]

    @gql_mapper.update_input(Employee)
    class EmployeeUpdate:
        __exclude__ = ["children"]

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def update_employee(input: EmployeeUpdate) -> EmployeeType:
            return EmployeeType(id=input.id, name=input.name)

    query = """
        mutation updateEmployee {
            updateEmployee(input: {id: 1, name: "bar"}) {
                id
                name
            }
        }
    """

    expected_schema = """
type EmployeeType {
  id: ID!
  name: String!
}

input EmployeeTypeUpdateInput {
  id: ID!
  name: String = null
}

type Mutation {
  updateEmployee(input: EmployeeTypeUpdateInput!): EmployeeType!
}

type Query {
  hello: String!
}
"""

    # Assert schema
    schema = strawberry.Schema(query=Query, mutation=Mutation)
    assert schema.as_str().strip() == expected_schema.strip()
    # Assert query result
    schema = strawberry.Schema(query=Query, mutation=Mutation)
    result = schema.execute_sync(query)
    assert result.data == {"updateEmployee": {"id": "1", "name": "bar"}}
