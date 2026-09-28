#!/usr/bin/env python3
"""serve.py - Thin FastAPI wrapper for the registered MLflow model."""
import os

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

from fastapi import FastAPI
from pydantic import BaseModel
import mlflow.pyfunc
import pandas as pd

app = FastAPI(title="Telco Churn Prediction API")

MODEL_URI = "models:/telco_churn_model/Production"
_model = None


@app.on_event("startup")
def load_model():
    global _model
    mlflow.set_tracking_uri("mlruns")
    _model = mlflow.pyfunc.load_model(MODEL_URI)
    print(f"Model loaded: {MODEL_URI}")


class ChurnRequest(BaseModel):
    features: dict


class ChurnResponse(BaseModel):
    churn_prediction: int
    model_uri: str


@app.post("/predict", response_model=ChurnResponse)
def predict(request: ChurnRequest):
    df = pd.DataFrame([request.features])
    prediction = _model.predict(df)
    return ChurnResponse(
        churn_prediction=int(prediction[0]),
        model_uri=MODEL_URI,
    )


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model is not None}
