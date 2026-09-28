# Task 1 - Track A: Data Science MLOps (Telco Churn)

## Setup

### Prerequisites
- Python 3.11+
- uv (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### One-command setup
```bash
uv sync
```

### Run everything
```bash
uv run python src/train.py      # Train 3 models, log to MLflow, register best
uv run python src/monitor.py    # Run drift monitoring (generates HTML reports)
uv run uvicorn src.serve:app --reload --port 5001  # Serve registered model
uv run mlflow ui --backend-store-uri mlruns        # View MLflow UI at http://127.0.0.1:5000
```


## a. Environment & Reproducibility (uv)

This project uses uv to resolve and lock the scikit-learn, Evidently AI 0.4 API, MLflow, pandas, and serving dependencies as one environment. The lock file records the complete dependency tree so a clean clone can reproduce the same environment with `uv sync`. The Evidently upper bound is required because the monitor uses the report API specified in the plan, which was removed in Evidently 0.5+.

## b. Experiment Tracking Strategy (MLflow)

The trainer runs exactly three model families in the `telco_churn_v1` experiment. Each run logs its hyperparameters, accuracy, precision, recall, F1, ROC-AUC, confusion matrix, ROC curve, and trained model artifact.

### Metrics

Run the trainer to populate this table with the actual MLflow metrics:

| Run | Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|-----|-------|----------|-----------|--------|-----|---------|
| 1 | Logistic Regression (C=1.0) | 0.8043 | 0.6535 | 0.5615 | 0.6040 | 0.8380 |
| 2 | Random Forest (n=100, d=10) | 0.7891 | 0.6408 | 0.4706 | 0.5427 | 0.8323 |
| 3 | Gradient Boosting (n=200, lr=0.05) | 0.7905 | 0.6343 | 0.5009 | 0.5598 | 0.8346 |

**Registered model**: Run 1 (Logistic Regression) was registered as `telco_churn_model` because it achieved the highest ROC-AUC (0.8380) and F1 (0.6040). ROC-AUC is used because the target is imbalanced and accuracy alone is misleading.

## c. Monitoring & Drift Strategy (Evidently AI)

The reference data is the training-time distribution and the current data is a held-out split with the plan's injected drift: a +15 mean shift in `MonthlyCharges`, more `Month-to-month` contracts, and 5% flipped `Churn` labels. The monitor flagged 2 drifted columns, including `MonthlyCharges` and `Contract`. The custom metric measured a reference mean of 64.60, a current mean of 80.42, and a difference of +15.82. The monitor writes data drift, target drift, and custom `MonthlyCharges` mean-comparison reports to `reports/` and logs them to the `telco_churn_drift` MLflow experiment.

The report's dataset-level drift flag was `False`, but the explicit column checks detected the two injected feature shifts. The `MonthlyCharges` increase indicates a changed customer price distribution, while the `Contract` shift increases the share of a higher-churn segment. Both findings would warrant retraining against the post-change production distribution.

## d. Orchestration (if implemented)

Airflow orchestration is implemented in `airflow/dags/churn_pipeline_dag.py` as a scheduled pipeline:
- **DAG ID**: `churn_drift_and_retrain`
- **Schedule**: `@weekly`
- **Tasks**:
  1. `drift_check`: Executes `uv run python src/monitor.py` to evaluate reference vs. incoming production data. If dataset-level drift is detected (`dataset_drift: True` in the output), an XCom flag `drift_detected` is set to `True`.
  2. `retrain_model`: Triggered downstream of `drift_check`. Reads the XCom flag; if drift was flagged, it runs `uv run python src/train.py` to retrain the candidate models on fresh data and register/promote the updated best model. If no drift is detected, retraining is skipped.

