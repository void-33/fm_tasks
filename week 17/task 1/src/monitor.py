#!/usr/bin/env python3
"""
monitor.py - Data drift and target drift monitoring with Evidently AI.
Run: uv run python src/monitor.py
"""
import os

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import mlflow
import numpy as np
import pandas as pd
from evidently import ColumnMapping
from evidently.metrics import ColumnDriftMetric, ColumnSummaryMetric
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
from evidently.report import Report
from sklearn.model_selection import train_test_split

DATA_PATH = "data/WA_Fn-UseC_-Telco-Customer-Churn.csv"
REPORTS_DIR = "reports"


def load_and_preprocess(path):
    """Reuse training preprocessing without one-hot encoding."""
    df = pd.read_csv(path)
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df.dropna(subset=["TotalCharges"], inplace=True)
    df.drop("customerID", axis=1, inplace=True)
    df["Churn"] = df["Churn"].map({"Yes": 1, "No": 0})
    return df


def create_reference_and_current(df):
    """Split data and inject numeric, categorical, and label drift."""
    reference, current = train_test_split(
        df, test_size=0.3, random_state=42, shuffle=True
    )
    current = current.copy()
    rng = np.random.RandomState(99)

    current["MonthlyCharges"] = current["MonthlyCharges"] + rng.normal(
        loc=15.0, scale=5.0, size=len(current)
    )

    mask_non_monthly = current["Contract"] != "Month-to-month"
    replacement_indices = current[mask_non_monthly].sample(
        frac=0.4, random_state=99
    ).index
    current.loc[replacement_indices, "Contract"] = "Month-to-month"

    flip_indices = current.sample(frac=0.05, random_state=99).index
    current.loc[flip_indices, "Churn"] = 1 - current.loc[flip_indices, "Churn"]
    return reference, current


def run_data_drift_report(reference, current, output_path):
    """Run the Evidently data drift report."""
    report = Report(
        metrics=[
            DataDriftPreset(),
            ColumnDriftMetric(column_name="MonthlyCharges"),
            ColumnDriftMetric(column_name="Contract"),
        ]
    )
    report.run(reference_data=reference, current_data=current)
    report.save_html(output_path)
    result = report.as_dict()
    drift_summary = result["metrics"][0]["result"]
    print(f"Data drift report saved: {output_path}")
    print(f"  Dataset drift detected: {drift_summary.get('dataset_drift')}")
    print(f"  Drifted columns: {drift_summary.get('number_of_drifted_columns')}")
    return result


def run_target_drift_report(reference, current, output_path):
    """Check whether the Churn rate shifted."""
    column_mapping = ColumnMapping(target="Churn", prediction=None)
    report = Report(metrics=[TargetDriftPreset()])
    report.run(
        reference_data=reference,
        current_data=current,
        column_mapping=column_mapping,
    )
    report.save_html(output_path)
    print(f"Target drift report saved: {output_path}")
    return report.as_dict()


def run_custom_metric_report(reference, current, output_path):
    """Report the reference/current mean MonthlyCharges difference."""
    report = Report(metrics=[ColumnSummaryMetric(column_name="MonthlyCharges")])
    report.run(reference_data=reference, current_data=current)
    report.save_html(output_path)
    result = report.as_dict()
    metric_result = result["metrics"][0]["result"]
    ref_mean = metric_result["reference_characteristics"]["mean"]
    cur_mean = metric_result["current_characteristics"]["mean"]
    diff = cur_mean - ref_mean
    print("Custom metric - MonthlyCharges:")
    print(f"  Reference mean: {ref_mean:.2f}")
    print(f"  Current mean:   {cur_mean:.2f}")
    print(f"  Difference:     {diff:+.2f}")
    return result


def log_drift_reports_to_mlflow(report_paths):
    mlflow.set_tracking_uri("mlruns")
    mlflow.set_experiment("telco_churn_drift")
    with mlflow.start_run(run_name="drift_monitoring"):
        for path in report_paths:
            mlflow.log_artifact(path, artifact_path="drift_reports")
            print(f"Logged artifact to MLflow: {path}")


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    df = load_and_preprocess(DATA_PATH)
    reference, current = create_reference_and_current(df)

    data_drift_path = f"{REPORTS_DIR}/data_drift_report.html"
    target_drift_path = f"{REPORTS_DIR}/target_drift_report.html"
    custom_metric_path = f"{REPORTS_DIR}/custom_metric_report.html"

    run_data_drift_report(reference, current, data_drift_path)
    run_target_drift_report(reference, current, target_drift_path)
    run_custom_metric_report(reference, current, custom_metric_path)
    log_drift_reports_to_mlflow(
        [data_drift_path, target_drift_path, custom_metric_path]
    )

    print("\nDrift monitoring complete.")
    print("Open reports in browser:")
    for path in [data_drift_path, target_drift_path, custom_metric_path]:
        print(f"  {path}")
    print("MLflow UI: uv run mlflow ui --backend-store-uri mlruns")


if __name__ == "__main__":
    main()
