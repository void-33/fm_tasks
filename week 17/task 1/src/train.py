#!/usr/bin/env python3
"""
train.py - Train 3 churn models and log everything to MLflow.
Run: uv run python src/train.py
"""
import os
import tempfile

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    RocCurveDisplay,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

DATA_PATH = "data/WA_Fn-UseC_-Telco-Customer-Churn.csv"


def load_and_preprocess(path):
    df = pd.read_csv(path)
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df.dropna(subset=["TotalCharges"], inplace=True)
    df.drop("customerID", axis=1, inplace=True)
    df["Churn"] = df["Churn"].map({"Yes": 1, "No": 0})
    return pd.get_dummies(df, drop_first=True)


def log_run(model, X_test, y_test, params: dict, run_name: str) -> dict:
    mlflow.log_params(params)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_proba),
    }
    mlflow.log_metrics(metrics)
    with tempfile.TemporaryDirectory() as tmpdir:
        fig, ax = plt.subplots()
        ConfusionMatrixDisplay.from_predictions(y_test, y_pred, ax=ax)
        ax.set_title(f"Confusion Matrix - {run_name}")
        cm_path = os.path.join(tmpdir, "confusion_matrix.png")
        fig.savefig(cm_path)
        plt.close(fig)
        mlflow.log_artifact(cm_path)

        fig2, ax2 = plt.subplots()
        RocCurveDisplay.from_predictions(y_test, y_proba, ax=ax2, name=run_name)
        roc_path = os.path.join(tmpdir, "roc_curve.png")
        fig2.savefig(roc_path)
        plt.close(fig2)
        mlflow.log_artifact(roc_path)

    mlflow.sklearn.log_model(
        model,
        artifact_path="model",
        skops_trusted_types=["sklearn.tree._tree.Tree"],
    )
    return metrics


def register_best_model():
    """Find and register the best run in the experiment."""
    client = mlflow.MlflowClient(tracking_uri="mlruns")
    experiment = client.get_experiment_by_name("telco_churn_v1")
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["metrics.roc_auc DESC"],
        max_results=1,
    )
    best_run = runs[0]
    best_run_id = best_run.info.run_id
    print(f"\nBest run: {best_run_id}")
    print(f"ROC-AUC: {best_run.data.metrics['roc_auc']:.4f}")
    print(f"F1: {best_run.data.metrics['f1']:.4f}")

    model_uri = f"runs:/{best_run_id}/model"
    registered = mlflow.register_model(model_uri=model_uri, name="telco_churn_model")
    print(f"Registered as version: {registered.version}")

    client.transition_model_version_stage(
        name="telco_churn_model",
        version=registered.version,
        stage="Staging",
    )
    print("Transitioned to: Staging")
    client.transition_model_version_stage(
        name="telco_churn_model",
        version=registered.version,
        stage="Production",
    )
    print("Transitioned to: Production")
    return registered


def main():
    mlflow.set_tracking_uri("mlruns")
    mlflow.set_experiment("telco_churn_v1")

    df = load_and_preprocess(DATA_PATH)
    X = df.drop("Churn", axis=1)
    y = df["Churn"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    with mlflow.start_run(run_name="logistic_regression_C1"):
        params = {
            "model": "LogisticRegression",
            "C": 1.0,
            "penalty": "l2",
            "solver": "lbfgs",
            "max_iter": 500,
        }
        model = LogisticRegression(
            C=1.0, penalty="l2", solver="lbfgs", max_iter=500, random_state=42
        )
        model.fit(X_train, y_train)
        metrics = log_run(model, X_test, y_test, params, "logistic_regression_C1")
        print(f"Run 1 (Logistic Regression): {metrics}")

    with mlflow.start_run(run_name="random_forest_d10"):
        params = {
            "model": "RandomForest",
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 5,
        }
        model = RandomForestClassifier(
            n_estimators=100, max_depth=10, min_samples_split=5, random_state=42
        )
        model.fit(X_train, y_train)
        metrics = log_run(model, X_test, y_test, params, "random_forest_d10")
        print(f"Run 2 (Random Forest): {metrics}")

    with mlflow.start_run(run_name="gradient_boosting_lr005"):
        params = {
            "model": "GradientBoosting",
            "n_estimators": 200,
            "learning_rate": 0.05,
            "max_depth": 4,
        }
        model = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4, random_state=42
        )
        model.fit(X_train, y_train)
        metrics = log_run(model, X_test, y_test, params, "gradient_boosting_lr005")
        print(f"Run 3 (Gradient Boosting): {metrics}")

    register_best_model()
    print("\nAll runs complete.")
    print("MLflow UI: uv run mlflow ui --backend-store-uri mlruns")


if __name__ == "__main__":
    main()
