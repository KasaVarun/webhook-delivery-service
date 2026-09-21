from fastapi import FastAPI, Request

app = FastAPI(title="Local Webhook Verification Receiver")


@app.post("/webhooks")
async def receive_webhook(request: Request) -> dict[str, object]:
    return {"received": await request.json()}