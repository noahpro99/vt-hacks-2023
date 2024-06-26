from contextlib import asynccontextmanager
import os
import openai
import numpy as np
import logging
import pandas as pd
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from detect import TFLiteModel, Point, TranscribeReq
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


ml_models = {}
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    model = TFLiteModel()
    ml_models["model"] = model
    yield
    ml_models.clear()
    


app = FastAPI(
    title="FastAPI AI Inference Server",
    description="FastAPI AI Inference Server",
    version="0.1.0",
    docs_url="/",
    redoc_url=None,
    lifespan=lifespan,
)

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# make fastapi load the model only once
# https://fastapi.tiangolo.com/advanced/on-startup-events/


@app.post("/transcribe")
async def predict(data: list[TranscribeReq]):
    THRESHOLD = 7
    outputs = []
    WINDOW_SIZE = 10
    STRIDE = 5
    print(len(data))
    # data = data[:: -1]

    if len(data) < WINDOW_SIZE:
        model_predict, confidence = ml_models['model'].predict(np.array(data))
        print(f"all frames: {model_predict}, {confidence}")
        return {"transcript": f"{model_predict}"}

    for i in range(0, len(data) - WINDOW_SIZE + 1, STRIDE):
        model_predict, confidence = ml_models['model'].predict(
            np.array(data[i:i+WINDOW_SIZE]))
        print(
            f"window of {i} to {i+WINDOW_SIZE}: {model_predict}, {confidence}")
        if (len(outputs) == 0 or (len(outputs) > 0 and outputs[len(outputs) - 1] != model_predict)) \
                and confidence > THRESHOLD:
            outputs.append(model_predict)

    # ask openai to interpret the outputs into what the sign language means in an english sentence
    print(f"outputs: {outputs}")

    if len(outputs) == 0:
        return {"transcript": ""}
    if len(outputs) == 1:
        return {"transcript": f"{outputs[0]}"}

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "Your role is to transcribe a list of sign language gestures into an english phrase"
            },
            {
                "role": "user",
                "content": "Hi there, I am trying to transcribe the following sign language gestures into an english phrase: " + " ".join(outputs) + "\n\n please output only one small english phrase"
            },
        ],
    )
    response_text = response.choices[0].message.content
    print(response_text)
    return {"transcript": f"{response_text}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)