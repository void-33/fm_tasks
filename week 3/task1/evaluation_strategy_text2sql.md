# Evaluation Strategy for the Text-to-SQL Agent

This document proposes a practical evaluation framework for the mini Text-to-SQL assignment in task 3 and task 4.

## 1. What We Should Measure

A Text-to-SQL agent should be judged on more than whether it can generate a syntactically valid query. The full pipeline has four parts:

1. Understand the natural-language question.
2. Generate SQL that matches the intent.
3. Execute the query successfully.
4. Return the right answer in a usable form.

That means evaluation should cover both SQL quality and end-to-end answer quality.

### Core metrics

- Execution success: does the SQL run without errors or blocking?
- Result correctness: do the query results match the reference answer?
- SQL validity: is it a safe SELECT query that respects the validator?
- Retry effectiveness: does the fix step recover from SQL errors?
- Summary quality: does the agent explain the result correctly in natural language?
- Robustness: how does the system behave on ambiguous, difficult, or malformed questions?
- Efficiency: how many retries are needed, and how long does the pipeline take?

## 2. Best-Fit Benchmark Style For This Assignment

For a small assignment like this, the most useful evaluation style is a hybrid of benchmark-style testing and run-time scoring.

### Recommended benchmark layers

#### A. Exact execution benchmark

This is the most important layer.

- Use a set of question/SQL pairs.
- Run the generated SQL against the live database.
- Compare the returned rows to the reference SQL output.
- Score the agent as correct only when the final result set matches.

#### B. Component benchmark

Measure whether the agent gets the right pieces of the query right.

- Correct table selection
- Correct column selection
- Correct join path
- Correct filter conditions
- Correct aggregation and grouping

This is useful when two SQL queries are not textually identical but are still logically equivalent.

#### C. Retry and recovery benchmark

The system should also be scored on whether the system can recover from mistakes.

- Did the first SQL fail?
- Did the fix step produce a working query?
- How many retries were needed?
- Did the final result become correct after repair?

#### D. Natural-language answer benchmark

The system should also be scored on whether the final explanation is faithful to the SQL result.

- Does the summary match the rows returned?
- Does it omit important facts?
- Does it hallucinate information not present in the result?

### Suggested task 3 metrics

- Execution Accuracy = successful executions / total examples
- Result Accuracy = exact result matches / total examples
- Retry Rate = examples that needed `fix_sql` / total examples
- Failure Breakdown = syntax, schema mismatch, join error, filter error, grouping error


### Suggested task 4 metrics

- Final SQL Success Rate
- Final Result Accuracy
- Retry Recovery Rate
- Average Number of Retries
- Summary Faithfulness Score
- Blocked Query Rate
- Mean Execution Time

## 3. Evaluation Framework

The simplest useful framework for this assignment is a three-stage scorecard.

### Stage 1: SQL generation quality

Use this for both task 3 and task 4.

- Is the query valid SQL?
- Is it a safe SELECT query?
- Does it use the right tables and columns?
- Does it produce the right rows?

### Stage 2: Agent recovery quality

Use this mainly for task 4.

- Did the first attempt fail?
- Did the fix step succeed?
- Did the agent need multiple retries?
- Did the final answer improve after retry?

### Stage 3: Response quality

Use this for task 4.

- Is the summary accurate?
- Is it concise and readable?
- Does it avoid hallucination?

## 4. A Practical Scoring Rubric

- 40 points: execution-based result correctness
- 20 points: table/column/join correctness
- 15 points: retry and recovery performance
- 15 points: natural-language summary quality
- 10 points: efficiency and safety

This keeps the evaluation aligned with the full agent pipeline rather than only SQL generation.

## 5.Rubric For Manual Review Of Hard Cases

Some questions will be ambiguous or have multiple valid SQL formulations. For those, exact string comparison is not enough.

Manual review can be used on a small subset and each case can be labelled as:

- correct and complete
- correct but incomplete
- partially correct
- incorrect
- failed to execute

This is especially useful for joins, aggregations, and natural-language summaries.


## 6.Conclusion

The best evaluation strategy for this project is execution-first evaluation with agent-level recovery scoring.

Use task 3 as the offline benchmark for SQL correctness and use task 4 to measure real agent behavior: retries, recovery, and final natural-language output. That combination gives a much more complete view of system quality than SQL text comparison alone.
