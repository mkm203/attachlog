"""GraphQL BFF: run with  uvicorn app.main:app --port 8003"""
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.schema import schema
from app.security import get_context

graphql_app = GraphQLRouter(schema, context_getter=get_context, graphql_ide="graphiql")

app = FastAPI(title="AttachLog GraphQL BFF", version="1.0.0",
              description="GraphQL facade over the placement and logbook REST services. "
                          "Get a token from the placement service (POST /v1/auth/login), then "
                          "use it as the Bearer token in the GraphiQL headers panel.")
app.include_router(graphql_app, prefix="/graphql")


@app.get("/health", tags=["health"])
def health():
    """Liveness/readiness probe."""
    return {"status": "ok", "service": "bff"}
