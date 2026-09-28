from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from datetime import datetime, timedelta
import subprocess

PROMOTION_THRESHOLD = 0.60
TASK2_ROOT = "/home/sakar/Documents/fusemachine/week 17/task 2"


def run_regression(**context):
    """Run Evidently regression evaluation and check pass rate."""
    result = subprocess.run(
        ["uv", "run", "python", "evidently_monitoring/regression_test.py"],
        capture_output=True,
        text=True,
        cwd=TASK2_ROOT,
        check=False,
    )
    print(result.stdout)

    # Extract highest percentage from test outputs
    best_pct = 0.0
    for line in result.stdout.splitlines():
        if "passed" in line and "%" in line:
            try:
                pct_str = line.split("(")[1].split("%")[0]
                pct = float(pct_str) / 100.0
                best_pct = max(best_pct, pct)
            except Exception:
                pass

    context["ti"].xcom_push(key="best_pct", value=best_pct)
    return best_pct


def branch_decision(**context):
    pct = context["ti"].xcom_pull(key="best_pct")
    if pct is not None and pct < PROMOTION_THRESHOLD:
        return "alert_regression"
    return "mark_passing"


def alert_regression(**context):
    pct = context["ti"].xcom_pull(key="best_pct")
    print(f"ALERT: Prompt regression detected! Best pass rate: {pct:.1%} < threshold {PROMOTION_THRESHOLD:.1%}")


def mark_passing(**context):
    pct = context["ti"].xcom_pull(key="best_pct")
    print(f"Regression check passed. Best pass rate: {pct:.1%}")


default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="agent_nightly_regression",
    default_args=default_args,
    description="Nightly regression evaluation for the cross-source verification agent",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["mlops", "agent"],
) as dag:
    regression = PythonOperator(
        task_id="run_regression",
        python_callable=run_regression,
    )
    branch = BranchPythonOperator(
        task_id="check_threshold",
        python_callable=branch_decision,
    )
    alert = PythonOperator(
        task_id="alert_regression",
        python_callable=alert_regression,
    )
    passing = PythonOperator(
        task_id="mark_passing",
        python_callable=mark_passing,
    )

    regression >> branch >> [alert, passing]
