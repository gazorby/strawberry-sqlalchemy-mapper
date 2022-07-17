import strawberry
from model import Model
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper

gql_mapper = StrawberrySQLAlchemyMapper(
    model_to_type_name=lambda name: f"{name.__name__}Type",
)

Base = declarative_base()


class Parent(Base, Model):
    __tablename__ = "parent"
    id = Column("id", Integer, primary_key=True)
    name = Column("name", String)
    children = relationship("Child")


class Child(Base, Model):
    __tablename__ = "child"
    id = Column("id", Integer, primary_key=True)
    name = Column("name", String)
    parent_id = Column(Integer, ForeignKey("parent.id"))


def test_basic_create():
    Base = declarative_base()

    class Parent(Base, Model):
        __tablename__ = "parent"
        id = Column("id", Integer, primary_key=True)
        name = Column("name", String)

    class Child(Base, Model):
        __tablename__ = "child"
        id = Column("id", Integer, primary_key=True)
        name = Column("name", String)

    @gql_mapper.type(Parent)
    class ParentType:
        id: strawberry.ID

    @gql_mapper.create_input(Parent)
    class ParentCreate:
        pass

    @gql_mapper.type(Child)
    class ChildType:
        id: strawberry.ID

    @gql_mapper.create_input(Child)
    class ChildCreate:
        pass

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def create_parent(input: ParentCreate) -> None:
            assert input == ParentCreate(name="foo")

    query = """
        mutation createParent {
            createParent(input: {name: "foo"})
        }
    """

    expected_schema = """
type Mutation {
  createParent(input: ParentTypeCreateInput!): Void
}

input ParentTypeCreateInput {
  name: String
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
    Base = declarative_base()

    class Parent(Base, Model):
        __tablename__ = "parent"
        id = Column("id", Integer, primary_key=True)
        name = Column("name", String)

    class Child(Base, Model):
        __tablename__ = "child"
        id = Column("id", Integer, primary_key=True)
        name = Column("name", String)

    @gql_mapper.type(Parent)
    class ParentType:
        id: strawberry.ID

    @gql_mapper.update_input(Parent)
    class ParentUpdate:
        pass

    @gql_mapper.type(Child)
    class ChildType:
        id: strawberry.ID

    @gql_mapper.update_input(Child)
    class ChildUpdate:
        pass

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def update_parent(input: ParentUpdate) -> None:
            assert input == ParentUpdate(id="1", name="foo")

    query = """
        mutation updateParent {
            updateParent(input: {id: 1, name: "foo"})
        }
    """

    expected_schema = """
type Mutation {
  updateParent(input: ParentTypeUpdateInput!): Void
}

input ParentTypeUpdateInput {
  id: ID!
  name: String = null
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
    @gql_mapper.type(Parent)
    class ParentType:
        id: strawberry.ID

        @gql_mapper.create_input(Parent)
        class Create:
            pass

    @gql_mapper.type(Child)
    class ChildType:
        id: strawberry.ID

        @gql_mapper.create_input(Child)
        class Create:
            __exclude__ = ["parent_id"]

    # important to call finalize here
    gql_mapper.finalize()

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def create_parent(input: ParentType.Create) -> None:
            assert input.name == "foo"
            assert input.children == [
                ChildType.Create(name="hello"),
                ChildType.Create(name="world"),
            ]

    query = """
        mutation createParent {
            createParent(
                input: {
                    name: "foo",
                    children: [
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
    # schema definition
    @gql_mapper.type(Parent)
    class ParentType:
        id: strawberry.ID
        __exclude__ = ["children"]

    @gql_mapper.create_input(Parent)
    class ParentCreate:
        __exclude__ = ["children"]

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def create_parent(input: ParentCreate) -> ParentType:
            return ParentType(id=1, name=input.name)

    query = """
        mutation createParent {
            createParent(input: {name: "foo"}) {
                id
                name
            }
        }
    """

    expected_schema = """
type Mutation {
  createParent(input: ParentTypeCreateInput!): ParentType!
}

type ParentType {
  id: ID!
  name: String
}

input ParentTypeCreateInput {
  name: String
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
    assert result.data == {"createParent": {"id": "1", "name": "foo"}}


def test_update_exclude():
    @gql_mapper.type(Parent)
    class ParentType:
        id: strawberry.ID

        __exclude__ = ["children"]

    @gql_mapper.update_input(Parent)
    class ParentUpdate:
        __exclude__ = ["children"]

    @strawberry.type
    class Query:
        hello: str = "Hello"

    @strawberry.type
    class Mutation:
        @strawberry.field
        def update_parent(input: ParentUpdate) -> ParentType:
            return ParentType(id=input.id, name=input.name)

    query = """
        mutation updateParent {
            updateParent(input: {id: 1, name: "bar"}) {
                id
                name
            }
        }
    """

    expected_schema = """
type Mutation {
  updateParent(input: ParentTypeUpdateInput!): ParentType!
}

type ParentType {
  id: ID!
  name: String
}

input ParentTypeUpdateInput {
  id: ID!
  name: String = null
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
    assert result.data == {"updateParent": {"id": "1", "name": "bar"}}
