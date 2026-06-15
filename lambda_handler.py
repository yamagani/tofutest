"""AWS Lambda entry point.

Adapts the FastAPI ASGI app to the Lambda runtime via Mangum. API Gateway
(HTTP API, payload format 2.0) invokes this handler; Mangum translates the
event into an ASGI request and the response back into an API Gateway response.
"""

from mangum import Mangum

from insurance_extractor.api import app

# lifespan="off": no startup/shutdown events to run in the Lambda model.
handler = Mangum(app, lifespan="off")
