from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess

TASK_ROOT = "/home/sakar/Documents/fusemachine/week 17/task 1"


def run_drift_check(**context):
    result = subprocess.run(
        ["uv", "run", "python", "src/monitor.py"],
        capture_output=True,
        text=True,
        cwd=TASK_ROOT,
        check=False,
    )
    print(result.stdout)
    context["ti"].xcom_push(
        key="drift_detected", value="dataset_drift: True" in result.stdout
    )
    return result.returncode


def run_retrain(**context):
    drift_detected = context["ti"].xcom_pull(key="drift_detected")
    if drift_detected:
        result = subprocess.run(
            ["uv", "run", "python", "src/train.py"],
            capture_output=True,
            text=True,
            cwd=TASK_ROOT,
            check=False,
        )
        print(result.stdout)
    else:
        print("No significant drift - skipping retraining.")


default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="churn_drift_and_retrain",
    default_args=default_args,
    description="Weekly churn drift check with conditional retraining",
    schedule_interval="@weekly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["mlops", "churn"],
) as dag:
    drift_check = PythonOperator(
        task_id="drift_check",
        python_callable=run_drift_check,
    )
    retrain = PythonOperator(
        task_id="retrain_model",
        python_callable=run_retrain,
    )
    drift_check >> retrain
