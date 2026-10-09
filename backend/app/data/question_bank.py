"""Curated question bank used when no LLM is available (and as a fallback when one fails).

Expected concepts use ``|`` to separate accepted synonyms; the first alternative is the label
shown in reports. ``probe`` is a natural follow-up used when an answer is incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BankQuestion:
    q: str
    difficulty: str
    concepts: tuple[str, ...]
    ideal: str
    probe: str = ""
    rubric: tuple[str, ...] = field(default=())


def Q(q: str, difficulty: str, concepts: list[str], ideal: str, probe: str = "") -> BankQuestion:  # noqa: N802
    return BankQuestion(q, difficulty, tuple(concepts), ideal, probe)


TECHNICAL: dict[str, list[BankQuestion]] = {
    "Python": [
        Q(
            "In Python, what's the difference between a list and a tuple, and when would you choose each?",
            "Easy",
            ["mutable|mutability", "immutable|immutability", "hashable|dictionary key", "performance|memory"],
            "Contrast mutability, explain that tuples are hashable and can be dict keys, mention use cases (fixed records vs growing collections) and minor memory/performance differences.",
            "Can a tuple ever contain something that changes? What happens if you try to use it as a dictionary key then?",
        ),
        Q(
            "Explain how Python generators work and when you would use one instead of building a list.",
            "Medium",
            ["yield", "lazy|lazily|on demand", "memory", "iterator|iteration", "stream|large file|large data"],
            "Describe yield and lazy evaluation, the iterator protocol, memory benefits for large or infinite streams, and a concrete example such as reading a large file line by line.",
            "What happens if you try to iterate over the same generator twice?",
        ),
        Q(
            "What is the GIL in CPython, and how does it affect how you'd speed up a CPU-bound versus an I/O-bound task?",
            "Hard",
            [
                "global interpreter lock|gil",
                "one thread|single thread",
                "cpu-bound|cpu bound",
                "multiprocessing|processes",
                "i/o-bound|io bound|asyncio|threads",
            ],
            "Define the GIL, explain that threads can't run Python bytecode in parallel, recommend multiprocessing or native extensions for CPU-bound work and threads/asyncio for I/O-bound work.",
            "Why do threads still help for I/O-bound work if only one thread runs Python code at a time?",
        ),
        Q(
            "How do decorators work in Python? Describe one you have written or used.",
            "Medium",
            [
                "function|callable",
                "wrapper|wraps",
                "higher-order|takes a function",
                "functools.wraps|wraps",
                "example|logging|timing|caching|auth",
            ],
            "Explain that a decorator is a callable taking a function and returning a wrapped one, show a concrete use (timing, caching, auth), and mention functools.wraps to keep metadata.",
        ),
    ],
    "Java": [
        Q(
            "What is the difference between an abstract class and an interface in Java?",
            "Easy",
            [
                "abstract class",
                "interface",
                "multiple inheritance|implement multiple",
                "state|fields",
                "default methods",
            ],
            "Compare state and constructors, single inheritance vs implementing multiple interfaces, default methods since Java 8, and when each is appropriate.",
        ),
        Q(
            "How does a HashMap work internally in Java, and what happens on a collision?",
            "Medium",
            [
                "hashcode|hash code",
                "buckets|array",
                "equals",
                "collision|linked list|chaining",
                "tree|treeify|red-black",
                "resize|load factor",
            ],
            "Walk through hashCode to bucket index, equals for key comparison, chaining on collisions (tree bins after a threshold), and resizing when the load factor is exceeded.",
            "What breaks if you override equals but not hashCode?",
        ),
        Q(
            "Explain how you'd make a piece of Java code thread-safe. Compare synchronized, locks and concurrent collections.",
            "Hard",
            [
                "synchronized",
                "lock|reentrantlock",
                "concurrenthashmap|concurrent collections",
                "race condition",
                "deadlock",
                "atomic|volatile",
            ],
            "Identify shared mutable state, explain race conditions, compare synchronized blocks, explicit locks and concurrent collections/atomics, and mention deadlock risks.",
        ),
    ],
    "JavaScript": [
        Q(
            "What's the difference between let, const and var in JavaScript?",
            "Easy",
            [
                "block scope|block-scoped",
                "function scope|function-scoped",
                "hoisting|hoisted",
                "reassign|reassignment",
                "temporal dead zone",
            ],
            "Explain function vs block scope, hoisting and the temporal dead zone, and that const prevents reassignment but not mutation.",
        ),
        Q(
            "Explain the JavaScript event loop. How do promises and setTimeout callbacks get scheduled?",
            "Medium",
            [
                "call stack",
                "event loop",
                "microtask|microtasks",
                "macrotask|task queue|callback queue",
                "single-threaded|single thread",
            ],
            "Describe the single-threaded call stack, the event loop, and that promise callbacks (microtasks) run before timer callbacks (macrotasks) once the stack is empty.",
            "If you call setTimeout with 0 and resolve a promise right after, which callback runs first and why?",
        ),
        Q(
            "What is a closure in JavaScript, and can you describe a real bug or feature where closures mattered?",
            "Medium",
            ["closure", "lexical scope|outer scope", "function", "example|counter|private|loop"],
            "Define a closure as a function retaining access to its lexical scope, give a concrete example (private state, event handlers, the classic var-in-loop bug).",
        ),
    ],
    "TypeScript": [
        Q(
            "What problems does TypeScript solve compared to plain JavaScript, and what are its limits?",
            "Easy",
            [
                "static types|type checking",
                "compile time|compile-time",
                "refactoring|tooling|autocomplete",
                "runtime|erased",
                "any",
            ],
            "Mention compile-time type checking, better tooling and refactoring, while noting types are erased at runtime so external data still needs validation.",
        ),
        Q(
            "Explain union types and type narrowing in TypeScript with an example.",
            "Medium",
            [
                "union",
                "narrowing|narrow",
                "typeof|instanceof|in operator",
                "discriminated union|discriminant",
                "type guard",
            ],
            "Define unions, show narrowing with typeof/instanceof/discriminant fields, and custom type guards.",
        ),
    ],
    "React": [
        Q(
            "What triggers a re-render in a React component, and how would you avoid unnecessary re-renders?",
            "Easy",
            ["state", "props", "parent re-render|parent renders", "memo|react.memo", "usememo|usecallback", "context"],
            "List state changes, new props, parent re-renders and context changes; mention React.memo, useMemo/useCallback, splitting components and measuring with the Profiler.",
            "How would you actually confirm that a component is re-rendering too often?",
        ),
        Q(
            "Explain how useEffect works, including the dependency array and cleanup function.",
            "Medium",
            [
                "side effect|side effects",
                "dependency array|dependencies",
                "cleanup",
                "after render",
                "stale|infinite loop",
            ],
            "Describe effects running after render, the dependency array controlling re-runs, cleanup on unmount/re-run (subscriptions, timers), and pitfalls like stale closures or infinite loops.",
            "What bug would you expect if you forgot the cleanup for a subscription or interval?",
        ),
        Q(
            "How would you manage state in a growing React app? When is local state enough and when do you reach for context or a library like Redux?",
            "Medium",
            [
                "local state|usestate",
                "lifting state|lift state",
                "context",
                "redux|zustand|store",
                "server state|react query",
            ],
            "Start with local state, lift state when shared, use context for low-frequency global data, a store for complex shared state, and a server-state cache for API data.",
        ),
        Q(
            "What are React keys, and what goes wrong if you use the array index as a key in a list that can be reordered?",
            "Hard",
            ["key", "reconciliation|diffing", "identity", "index", "state mismatch|wrong state|reorder"],
            "Explain keys give elements stable identity during reconciliation; index keys break when items are inserted or reordered, causing state to attach to the wrong item.",
        ),
    ],
    "Node.js": [
        Q(
            "How does Node.js handle many concurrent requests with a single thread?",
            "Medium",
            ["event loop", "non-blocking|asynchronous|async", "libuv|thread pool", "i/o", "cpu-bound|blocking"],
            "Describe the event loop with non-blocking I/O via libuv, the thread pool for some operations, and why CPU-heavy work blocks everyone (use worker threads or offload).",
        ),
        Q(
            "How would you structure error handling in an Express or Node API?",
            "Easy",
            ["middleware", "try/catch|try catch", "async errors|promise", "status code", "logging"],
            "Mention centralized error-handling middleware, catching async errors, mapping to proper status codes, logging, and not leaking stack traces.",
        ),
    ],
    "Flask": [
        Q(
            "Walk me through what happens when a request hits a Flask endpoint, from routing to response.",
            "Easy",
            ["wsgi", "routing|route", "request context", "view function", "response"],
            "Explain the WSGI server passing the request, URL routing to a view, request/app contexts, the view returning a response that is serialized back.",
        ),
        Q(
            "How would you structure a larger Flask application so it stays maintainable?",
            "Medium",
            ["blueprints", "application factory|create_app", "configuration|config", "orm|sqlalchemy", "tests|testing"],
            "Use an application factory, blueprints per domain, environment-based config, an ORM layer and services, and tests with the test client.",
        ),
        Q(
            "Flask's development server isn't meant for production. How would you deploy and scale a Flask API?",
            "Hard",
            [
                "gunicorn|uwsgi",
                "workers",
                "reverse proxy|nginx",
                "stateless",
                "database connections|connection pool",
                "horizontal|load balancer",
            ],
            "Run under Gunicorn with multiple workers behind Nginx, keep the app stateless, manage DB connection pooling, and scale horizontally behind a load balancer.",
        ),
    ],
    "Django": [
        Q(
            "How does Django's ORM help you, and when would you drop down to raw SQL?",
            "Medium",
            ["orm", "queryset|lazy", "n+1|select_related|prefetch_related", "migrations", "raw sql"],
            "Explain lazy querysets, avoiding N+1 with select_related/prefetch_related, migrations, and using raw SQL for complex or performance-critical queries.",
        ),
        Q(
            "Explain Django's request/response cycle including middleware.",
            "Easy",
            ["urls|url routing", "view", "middleware", "template|serializer", "response"],
            "Request passes middleware, URL resolver picks a view, view uses models/templates, response passes back through middleware.",
        ),
    ],
    "FastAPI": [
        Q(
            "What makes FastAPI different from Flask, and how does it use type hints?",
            "Medium",
            ["type hints", "pydantic|validation", "async|asgi", "openapi|docs", "dependency injection|depends"],
            "Mention ASGI/async support, Pydantic validation from type hints, auto-generated OpenAPI docs and dependency injection.",
        ),
    ],
    "Spring Boot": [
        Q(
            "What does Spring Boot's dependency injection give you, and how do you structure a typical REST service in it?",
            "Medium",
            ["dependency injection|di|ioc", "bean|beans", "controller", "service", "repository"],
            "Explain IoC/DI with beans, and a controller-service-repository layering with configuration via properties.",
        ),
    ],
    "SQL": [
        Q(
            "What's the difference between INNER JOIN and LEFT JOIN? Give an example where the choice matters.",
            "Easy",
            ["inner join", "left join", "matching rows|both tables", "null|nulls", "example"],
            "INNER returns only matching rows; LEFT keeps all rows from the left table with NULLs for non-matches. Example: customers with zero orders appear only with LEFT JOIN.",
        ),
        Q(
            "How would you find the second-highest salary in each department using SQL?",
            "Medium",
            ["group by|partition by", "window function|dense_rank|row_number|rank", "subquery", "ties|duplicates"],
            "Use a window function such as DENSE_RANK() OVER (PARTITION BY department ORDER BY salary DESC) and filter rank = 2, discussing ties; or a correlated subquery.",
            "How does your query behave when two people tie for the highest salary?",
        ),
        Q(
            "A query that used to take 50 ms now takes 5 seconds. How do you investigate and fix it?",
            "Hard",
            [
                "explain|query plan|explain analyze",
                "index|indexes",
                "full table scan|sequential scan",
                "statistics|analyze",
                "data growth|volume",
                "n+1|joins",
            ],
            "Reproduce, run EXPLAIN/ANALYZE, look for sequential scans or bad joins, check indexes and statistics, consider data growth and query rewrites, then verify with before/after timings.",
            "Suppose EXPLAIN shows a sequential scan on a large table. What would you check next?",
        ),
    ],
    "Database Design": [
        Q(
            "How do database indexes work, and what's the cost of adding too many?",
            "Medium",
            [
                "b-tree|btree|balanced tree",
                "lookup|search faster|faster reads",
                "write|insert|update",
                "storage|space",
                "selectivity|cardinality",
            ],
            "Explain B-tree indexes speeding lookups, the write amplification and storage cost, choosing columns by query patterns and selectivity, and composite index ordering.",
            "Which columns would you index for a query that filters by user and sorts by created date?",
        ),
        Q(
            "What is database normalization, and when might you intentionally denormalize?",
            "Easy",
            [
                "normal form|1nf|2nf|3nf",
                "redundancy|duplication",
                "anomalies|consistency",
                "denormalize|denormalization",
                "read performance|reporting",
            ],
            "Explain removing redundancy via normal forms to avoid update anomalies; denormalize for read-heavy or reporting workloads with the consistency trade-off.",
        ),
        Q(
            "Explain ACID transactions and give an example of a bug that isolation levels prevent.",
            "Hard",
            [
                "atomicity",
                "consistency",
                "isolation",
                "durability",
                "isolation level|read committed|serializable",
                "dirty read|lost update|race",
            ],
            "Define each ACID property, describe isolation levels and anomalies (dirty reads, lost updates), with an example such as two concurrent balance updates.",
        ),
    ],
    "PostgreSQL": [
        Q(
            "Why would you choose PostgreSQL for a project, and what features of it have you actually used?",
            "Easy",
            ["relational|acid", "json|jsonb", "indexes", "constraints|foreign keys", "extensions|full-text"],
            "Mention ACID guarantees, rich SQL, constraints, JSONB, index types and extensions, tied to a concrete use.",
        ),
    ],
    "MongoDB": [
        Q(
            "When would you choose MongoDB over a relational database, and what do you give up?",
            "Medium",
            [
                "document|schema-less|flexible schema",
                "joins",
                "transactions|consistency",
                "embedding|denormalization",
                "scaling|sharding",
            ],
            "Flexible document schema, embedding related data, horizontal scaling via sharding; trade-offs in joins, multi-document transactions and schema discipline.",
        ),
    ],
    "Redis": [
        Q(
            "What is Redis good for, and how would you use it as a cache in front of a database?",
            "Medium",
            [
                "in-memory",
                "cache-aside|lazy loading",
                "ttl|expiration",
                "invalidation",
                "data structures|sorted sets|pub/sub",
            ],
            "In-memory key-value store; cache-aside with TTLs, invalidation on writes, eviction policy, and other uses like rate limiting, sessions or queues.",
            "What happens to your users when the cache and the database disagree, and how do you prevent it?",
        ),
    ],
    "Caching": [
        Q(
            "Caching is famously hard to get right. What can go wrong with a cache and how do you handle it?",
            "Hard",
            [
                "invalidation",
                "stale data|staleness",
                "ttl|expiry",
                "stampede|thundering herd",
                "consistency",
                "eviction|lru",
            ],
            "Discuss invalidation strategies, TTLs, stale reads, cache stampedes (locking, request coalescing, jitter), eviction policies and measuring hit rate.",
        ),
    ],
    "REST APIs": [
        Q(
            "What makes an API RESTful? Walk me through how you'd design endpoints for a simple resource like orders.",
            "Easy",
            [
                "resources|nouns",
                "http methods|get|post|put|delete",
                "status codes",
                "stateless",
                "pagination|filtering",
            ],
            "Resource-oriented URLs, proper HTTP methods and status codes, statelessness, pagination/filtering, and versioning; example /orders and /orders/{id}.",
            "Which status codes would you return for a validation error versus a missing order?",
        ),
        Q(
            "What's the difference between PUT and PATCH, and what does idempotency mean for API design?",
            "Medium",
            ["put", "patch", "idempotent|idempotency", "retries|retry", "post"],
            "PUT replaces a resource and is idempotent; PATCH applies partial updates; idempotency makes retries safe; POST is not idempotent unless you add idempotency keys.",
        ),
        Q(
            "How would you version and evolve a public API without breaking existing clients?",
            "Hard",
            [
                "versioning|v1|version",
                "backward compatible|backwards compatibility",
                "deprecation",
                "additive changes",
                "documentation|contract",
            ],
            "Prefer additive, backward-compatible changes; version via URL or headers for breaking changes; deprecation windows and communication; contract tests and docs.",
        ),
    ],
    "Authentication": [
        Q(
            "How does JWT-based authentication work, and what are its security trade-offs compared to server sessions?",
            "Medium",
            [
                "token|jwt",
                "signature|signed",
                "stateless",
                "expiry|expiration",
                "revocation|logout",
                "storage|httponly|cookie",
            ],
            "Server signs a token with claims, client sends it on each request, server verifies the signature; trade-offs: hard revocation, need short expiry and refresh tokens, secure storage (httpOnly cookies).",
            "If a user's JWT is stolen, what can you do about it?",
        ),
        Q(
            "What's the difference between authentication and authorization, and how did you implement role-based access control?",
            "Easy",
            [
                "authentication|who you are",
                "authorization|what you can do",
                "roles|rbac",
                "permissions",
                "middleware|check",
            ],
            "Authentication proves identity; authorization decides permissions; RBAC maps roles to permissions enforced server-side, e.g. in middleware or decorators.",
        ),
        Q(
            "How should passwords be stored, and what else would you do to protect a login endpoint?",
            "Medium",
            ["hash|hashing", "salt", "bcrypt|argon2|scrypt", "rate limiting|lockout", "https|tls"],
            "Hash with a slow salted algorithm (bcrypt/argon2), never encrypt or store plaintext; add rate limiting, lockout/MFA and TLS.",
        ),
    ],
    "Git": [
        Q(
            "How do you use Git branches in a team, and how do you resolve a merge conflict?",
            "Easy",
            ["branch|branches", "pull request|code review", "merge|rebase", "conflict", "communicate|test"],
            "Feature branches with pull requests and reviews; resolve conflicts by understanding both changes, editing, testing and committing; rebase vs merge trade-offs.",
        ),
        Q(
            "What's the difference between git merge and git rebase, and when would you avoid rebasing?",
            "Medium",
            ["merge commit", "rebase|rewrite history", "linear history", "shared branch|public branch", "force push"],
            "Merge preserves history with a merge commit; rebase replays commits for linear history but rewrites hashes, so avoid rebasing shared branches.",
        ),
    ],
    "Docker": [
        Q(
            "What problem does Docker solve, and what's the difference between an image and a container?",
            "Easy",
            ["image", "container", "environment|consistency|works on my machine", "isolation", "layers"],
            "Docker packages an app with its dependencies for consistent environments; an image is the immutable layered template, a container is a running instance.",
        ),
        Q(
            "How would you write a Dockerfile for a production web app so the image is small and secure?",
            "Medium",
            ["multi-stage", "base image|slim|alpine", "layer caching|cache", "non-root", "secrets|env"],
            "Multi-stage builds, slim base images, ordering layers for caching, running as non-root, not baking secrets into images, .dockerignore.",
        ),
    ],
    "Kubernetes": [
        Q(
            "Explain pods, deployments and services in Kubernetes and how traffic reaches your app.",
            "Medium",
            ["pod", "deployment|replicas", "service", "ingress|load balancer", "health checks|probes"],
            "Pods run containers, deployments manage replica sets and rollouts, services provide stable networking, ingress routes external traffic; readiness/liveness probes.",
        ),
    ],
    "AWS": [
        Q(
            "Which AWS services would you use to host a simple web app with a database, and why?",
            "Easy",
            ["ec2|ecs|lambda|elastic beanstalk", "rds|database", "s3", "security groups|iam", "load balancer|alb"],
            "Compute (EC2/ECS/Lambda), managed database (RDS), S3 for static assets, IAM and security groups for access, a load balancer and CloudWatch for monitoring.",
        ),
    ],
    "CI/CD": [
        Q(
            "Describe a CI/CD pipeline you've built or would build. What should run on every pull request?",
            "Medium",
            ["build", "tests|unit tests", "lint", "deploy|deployment", "rollback|staging"],
            "On PRs: install, lint, type-check, unit/integration tests and build; on merge: deploy to staging then production with rollback and monitoring.",
        ),
    ],
    "Testing": [
        Q(
            "How do you decide what to unit test versus integration test? Give an example from your work.",
            "Medium",
            ["unit test|unit tests", "integration test|integration tests", "mock|mocking", "edge cases", "coverage"],
            "Unit-test pure logic and edge cases with mocks at boundaries; integration-test interactions with DB/APIs; coverage as a signal not a goal; concrete example.",
            "What's one bug a unit test would miss but an integration test would catch?",
        ),
    ],
    "Data Structures": [
        Q(
            "When would you use a hash map versus a sorted structure like a balanced tree? What are the complexities?",
            "Easy",
            ["hash map|hash table", "o(1)|constant", "o(log n)|log n", "ordering|sorted|range queries", "collisions"],
            "Hash maps give average O(1) lookup with no ordering; balanced trees give O(log n) with ordered traversal and range queries.",
        ),
        Q(
            "Explain the difference between a stack and a queue and give a real use case for each.",
            "Easy",
            [
                "lifo|last in first out",
                "fifo|first in first out",
                "undo|call stack|backtracking",
                "bfs|scheduling|buffer",
            ],
            "Stack is LIFO (undo, call stack, DFS); queue is FIFO (BFS, job scheduling, buffering).",
        ),
        Q(
            "How would you detect a cycle in a linked list, and what's the time and space complexity?",
            "Medium",
            ["two pointers|fast and slow|floyd", "o(n)", "o(1) space|constant space", "hash set|visited"],
            "Floyd's fast/slow pointers detect a cycle in O(n) time and O(1) space; alternative with a visited set uses O(n) space.",
        ),
    ],
    "Object-Oriented Programming": [
        Q(
            "Explain encapsulation, inheritance and polymorphism with an example from code you've written.",
            "Easy",
            ["encapsulation", "inheritance", "polymorphism", "abstraction", "example"],
            "Define each pillar briefly and anchor in a concrete example; mention composition over inheritance.",
        ),
        Q(
            "When would you prefer composition over inheritance?",
            "Medium",
            ["composition", "inheritance", "coupling|tight coupling", "flexibility|swap", "is-a|has-a"],
            "Inheritance models is-a but couples tightly; composition (has-a) is more flexible, easier to test and change; example.",
        ),
    ],
    "Machine Learning": [
        Q(
            "How do you detect and handle overfitting?",
            "Easy",
            [
                "overfitting",
                "validation|train/test split|holdout",
                "cross-validation",
                "regularization",
                "more data|simpler model|early stopping",
            ],
            "Compare training vs validation performance, use cross-validation, regularization, simpler models, early stopping and more data.",
        ),
        Q(
            "Your classifier has 95% accuracy but the business says it's useless. What might be going on?",
            "Medium",
            ["class imbalance|imbalanced", "precision", "recall", "f1|confusion matrix", "baseline|business metric"],
            "Likely class imbalance; accuracy hides poor minority-class performance; use precision/recall/F1, confusion matrix, compare with a baseline and align with the business metric.",
            "Which metric would you optimize if false negatives were much more costly than false positives?",
        ),
        Q(
            "How would you take a model from a notebook to production and keep it healthy?",
            "Hard",
            [
                "serving|api|endpoint",
                "versioning",
                "monitoring",
                "data drift|drift",
                "retraining",
                "reproducibility|pipeline",
            ],
            "Package and serve behind an API, version data/models, monitor latency and prediction quality, detect drift, retrain via reproducible pipelines.",
        ),
    ],
    "Deep Learning": [
        Q(
            "Explain what happens during backpropagation and why learning rate matters.",
            "Medium",
            ["gradient|gradients", "chain rule", "loss", "learning rate", "convergence|diverge"],
            "Compute loss, propagate gradients back via the chain rule, update weights; too high LR diverges, too low converges slowly.",
        ),
    ],
    "NLP": [
        Q(
            "How would you build an intent classifier for a chatbot, and how would you evaluate it?",
            "Medium",
            [
                "labelled data|labeled data|dataset",
                "features|tf-idf|embeddings",
                "model|classifier",
                "precision|recall|f1|confusion matrix",
                "fallback|unknown intent|threshold",
            ],
            "Collect labelled utterances, vectorize (TF-IDF or embeddings), train a classifier, evaluate with per-class precision/recall on a held-out set, and add a confidence threshold for fallback.",
        ),
    ],
    "LLMs": [
        Q(
            "What are the main risks of putting an LLM into a product, and how do you mitigate them?",
            "Medium",
            ["hallucination", "prompt injection", "evaluation|evals", "cost|latency", "privacy|data"],
            "Hallucinations (grounding, validation), prompt injection (treat input as data, restrict tools), evaluation sets, cost/latency control and data privacy.",
        ),
    ],
    "Statistics": [
        Q(
            "Explain what a p-value means in an A/B test, and a common way people misinterpret it.",
            "Medium",
            [
                "null hypothesis",
                "probability",
                "significance|alpha|0.05",
                "misinterpret|not the probability",
                "sample size|power",
            ],
            "Probability of observing data at least as extreme assuming the null is true; not the probability the hypothesis is true; mention significance level, power and sample size.",
        ),
        Q(
            "When would you use the median instead of the mean?",
            "Easy",
            ["outliers", "skewed|skew", "mean", "median", "example|income|salary|latency"],
            "Use the median for skewed distributions or with outliers (income, latency); the mean is sensitive to extreme values.",
        ),
    ],
    "Data Analysis": [
        Q(
            "Walk me through how you'd approach a vague question like 'why did sales drop last month?'",
            "Medium",
            [
                "clarify|define",
                "segment|breakdown",
                "data quality",
                "hypotheses|hypothesis",
                "seasonality|trend",
                "communicate|recommendation",
            ],
            "Clarify the metric and time window, check data quality, segment (region, channel, product), form and test hypotheses, consider seasonality, and communicate findings with a recommendation.",
        ),
        Q(
            "How do you clean a messy dataset before analysis?",
            "Easy",
            ["missing values", "duplicates", "outliers", "data types|formats", "validation|sanity checks"],
            "Profile the data, handle missing values, remove duplicates, fix types/formats, investigate outliers, and validate against known totals.",
        ),
    ],
    "Pandas": [
        Q(
            "How would you find the top 3 products by revenue per region in Pandas?",
            "Medium",
            ["groupby", "sum|agg", "sort_values|nlargest", "head|rank", "reset_index"],
            "groupby region and product, sum revenue, then sort and take head(3) per group or use nlargest/rank.",
        ),
    ],
    "Excel": [
        Q(
            "Which Excel features do you rely on for analysis, and when would you move from Excel to SQL or Python?",
            "Easy",
            [
                "pivot table|pivot tables",
                "vlookup|xlookup|index match",
                "formulas",
                "charts",
                "scale|large data|automation",
            ],
            "Pivot tables, lookups, conditional formulas and charts; move to SQL/Python for large data, reproducibility and automation.",
        ),
    ],
    "Data Visualization": [
        Q(
            "How do you decide which chart to use, and how do you design a dashboard people actually use?",
            "Medium",
            [
                "audience",
                "comparison|trend|distribution",
                "bar|line|histogram",
                "kpi|key metrics",
                "clutter|simplicity",
            ],
            "Start from audience and question, choose charts by intent (trend: line, comparison: bar, distribution: histogram), highlight KPIs, minimize clutter.",
        ),
    ],
    "Linux": [
        Q(
            "A service on a Linux server is slow. Which commands would you use to investigate?",
            "Medium",
            ["top|htop", "memory|free", "disk|df|iostat", "logs|journalctl|tail", "network|netstat|ss"],
            "Check CPU/memory (top/htop, free), disk (df, iostat), logs (journalctl, tail), network (ss, netstat) and the process itself.",
        ),
    ],
    "HTML": [
        Q(
            "Why does semantic HTML matter? Give examples of semantic elements and what they help with.",
            "Easy",
            ["semantic", "accessibility|screen readers", "seo", "header|nav|main|article|button", "meaning|structure"],
            "Semantic elements convey meaning to browsers, assistive tech and search engines; examples nav, main, article, button vs div.",
        ),
    ],
    "CSS": [
        Q(
            "Explain the CSS box model and the difference between flexbox and grid.",
            "Easy",
            ["content", "padding", "border", "margin", "box-sizing", "flexbox|one-dimensional", "grid|two-dimensional"],
            "Content, padding, border, margin and box-sizing; flexbox for one-dimensional layouts, grid for two-dimensional.",
        ),
    ],
    "Accessibility": [
        Q(
            "How do you make a custom dropdown or modal accessible?",
            "Hard",
            ["keyboard|focus", "aria|role", "focus trap|focus management", "screen reader", "escape|close"],
            "Use native elements when possible; otherwise roles/ARIA attributes, keyboard navigation, focus management/trap, Escape to close, screen-reader testing.",
        ),
    ],
    "Web Performance": [
        Q(
            "A page loads slowly. How do you find out why and fix it?",
            "Medium",
            [
                "lighthouse|devtools|profil",
                "bundle size|code splitting",
                "images|lazy loading",
                "caching|cdn",
                "core web vitals|lcp|cls",
            ],
            "Measure with Lighthouse/DevTools, look at Core Web Vitals, reduce bundle size via code splitting, optimize images and lazy-load, use caching and a CDN.",
        ),
    ],
    "Microservices": [
        Q(
            "When do microservices make sense versus a monolith, and what new problems do they introduce?",
            "Hard",
            [
                "monolith",
                "independent deployment|deploy independently",
                "team boundaries|ownership",
                "network|latency",
                "distributed transactions|consistency",
                "observability|monitoring",
            ],
            "Microservices help with independent deployment and team ownership at scale; costs: network latency/failures, data consistency, observability, operational overhead; start with a modular monolith.",
            "How would you keep data consistent when one business action touches two services?",
        ),
    ],
    "Kafka": [
        Q(
            "Why would you put a message queue such as Kafka or RabbitMQ between two services?",
            "Medium",
            [
                "decouple|decoupling",
                "asynchronous|async",
                "buffer|spikes|backpressure",
                "retries|durability",
                "ordering|idempotent consumers",
            ],
            "Decouple producers and consumers, absorb spikes, enable async processing and retries; consider ordering, delivery guarantees and idempotent consumers.",
        ),
    ],
    "Security": [
        Q(
            "Name a few common web security vulnerabilities and how you defend against them.",
            "Medium",
            [
                "sql injection|parameterized",
                "xss|cross-site scripting|escaping",
                "csrf",
                "authentication|authorization",
                "secrets|input validation",
            ],
            "SQL injection (parameterized queries), XSS (escaping, CSP), CSRF (tokens, SameSite), broken auth, secret management and input validation.",
        ),
    ],
    "Agile": [
        Q(
            "What does a good sprint look like from your perspective, and what do you do when scope changes mid-sprint?",
            "Easy",
            [
                "planning|estimation",
                "standup|communication",
                "scope|priorities",
                "retrospective",
                "product owner|stakeholders",
            ],
            "Clear planning with estimates, daily communication, protect scope but renegotiate with the product owner when priorities change, learn in retrospectives.",
        ),
    ],
    "Product Management": [
        Q(
            "How do you prioritize a backlog when engineering, sales and customers all want different things?",
            "Medium",
            [
                "impact|value",
                "effort|cost",
                "framework|rice|moscow",
                "data|metrics",
                "strategy|goals",
                "stakeholders|communicate",
            ],
            "Tie to strategy and goals, score impact vs effort (e.g. RICE), use data and customer evidence, communicate trade-offs transparently to stakeholders.",
        ),
        Q(
            "How would you measure the success of a new feature after launch?",
            "Easy",
            ["success metric|kpi", "baseline", "adoption|usage", "a/b test|experiment", "guardrail|retention"],
            "Define a primary metric and guardrails before launch, establish a baseline, track adoption/retention, run an experiment where possible.",
        ),
    ],
    "C++": [
        Q(
            "What is RAII in C++ and why is it important?",
            "Medium",
            [
                "resource acquisition is initialization|raii",
                "constructor",
                "destructor",
                "scope",
                "smart pointers|unique_ptr|shared_ptr",
            ],
            "Resources are tied to object lifetime: acquired in constructors, released in destructors when leaving scope; smart pointers apply RAII to memory.",
        ),
    ],
    "Go": [
        Q(
            "How do goroutines and channels work in Go, and how do you avoid leaking goroutines?",
            "Medium",
            ["goroutine", "channel", "lightweight|scheduler", "context|cancellation", "leak|blocked"],
            "Goroutines are lightweight threads scheduled by the runtime; channels communicate between them; use context for cancellation to avoid blocked/leaked goroutines.",
        ),
    ],
}

# Skills without their own questions borrow from the closest curated topic.
BANK_ALIASES: dict[str, str] = {
    "MySQL": "Database Design",
    "SQLite": "Database Design",
    "Oracle": "Database Design",
    "SQL Server": "Database Design",
    "Express": "Node.js",
    "Next.js": "React",
    "Redux": "React",
    "Tableau": "Data Visualization",
    "Power BI": "Data Visualization",
    "Matplotlib": "Data Visualization",
    "RabbitMQ": "Kafka",
    "Bash": "Linux",
    "scikit-learn": "Machine Learning",
    "PyTorch": "Deep Learning",
    "TensorFlow": "Deep Learning",
    "Hugging Face": "NLP",
    "LangChain": "LLMs",
    "NumPy": "Pandas",
    "Pytest": "Testing",
    "Jest": "Testing",
    "JUnit": "Testing",
    "Playwright": "Testing",
    "Selenium": "Testing",
    "GitHub Actions": "CI/CD",
    "Jenkins": "CI/CD",
    "Responsive Design": "CSS",
    "Tailwind CSS": "CSS",
    "Bootstrap": "CSS",
    "Azure": "AWS",
    "GCP": "AWS",
    "Terraform": "CI/CD",
    "System Design": "Microservices",
    "Cassandra": "MongoDB",
    "DynamoDB": "MongoDB",
    "Firebase": "MongoDB",
    "Stakeholder Management": "Product Management",
    "Monitoring": "Linux",
    "Networking": "REST APIs",
}


def bank_for_skill(skill: str) -> list[BankQuestion]:
    return TECHNICAL.get(skill) or TECHNICAL.get(BANK_ALIASES.get(skill, ""), [])


# Generic, skill-agnostic fallback when a skill has no curated questions.
GENERIC_SKILL = [
    Q(
        "How have you used {skill} in practice? Walk me through a specific example and one problem you ran into.",
        "Easy",
        [
            "specific example|project",
            "what you did|my role|i built|i used",
            "problem|challenge|issue",
            "solution|fixed|resolved",
        ],
        "Pick one concrete project, explain what you used {skill} for, a real problem you hit and how you solved it, and what you learned.",
    ),
    Q(
        "What are the main trade-offs or limitations of {skill}, and when would you choose something else?",
        "Medium",
        ["trade-off|tradeoff", "limitation|downside", "alternative", "when to use|use case"],
        "Name concrete strengths and limitations of {skill}, compare with one alternative, and state when each fits.",
    ),
]

CODING = [
    Q(
        "Given an array of integers and a target, how would you find two numbers that add up to the target? Talk me through your approach and its complexity.",
        "Easy",
        [
            "brute force|nested loop",
            "hash map|hash set|dictionary",
            "o(n)",
            "o(n^2)|quadratic",
            "edge cases|duplicates",
        ],
        "Start with the O(n^2) brute force, then use a hash map of seen values for O(n) time and O(n) space; discuss duplicates and no-solution cases.",
        "What changes if the array is already sorted?",
    ),
    Q(
        "How would you check whether a string of brackets like '([]{})' is balanced?",
        "Easy",
        ["stack", "push|pop", "matching|pairs", "o(n)", "empty|edge cases"],
        "Push opening brackets on a stack, pop and compare on closing brackets, valid if the stack is empty at the end; O(n).",
    ),
    Q(
        "How would you find the first non-repeating character in a string?",
        "Easy",
        ["count|frequency|hash map", "two passes|second pass", "o(n)", "order"],
        "Count frequencies in one pass, then scan again to find the first char with count 1; O(n) time, O(k) space.",
    ),
    Q(
        "How would you merge overlapping intervals, for example [[1,3],[2,6],[8,10]]?",
        "Medium",
        ["sort|sorting", "start time|by start", "merge|overlap", "o(n log n)", "edge cases|touching"],
        "Sort by start, iterate and merge when the next start <= current end; O(n log n) due to sorting.",
        "How would you handle intervals that only touch, like [1,2] and [2,3]?",
    ),
    Q(
        "Design an LRU cache with O(1) get and put. What data structures would you use?",
        "Hard",
        [
            "hash map|dictionary",
            "doubly linked list|linked list",
            "o(1)",
            "eviction|least recently used",
            "move to front|update order",
        ],
        "Combine a hash map (key -> node) with a doubly linked list ordered by recency; move accessed nodes to the front and evict from the tail; both ops O(1).",
    ),
    Q(
        "How would you find the k most frequent elements in a large list?",
        "Medium",
        ["count|frequency|hash map", "heap|priority queue", "o(n log k)", "bucket sort"],
        "Count with a hash map, then use a min-heap of size k for O(n log k), or bucket sort by frequency for O(n).",
    ),
    Q(
        "Explain how binary search works and a bug people commonly introduce when implementing it.",
        "Easy",
        ["sorted", "middle|mid", "halve|half", "o(log n)", "off-by-one|overflow|infinite loop"],
        "Requires sorted input, compare with the middle and discard half each step, O(log n); common bugs: off-by-one bounds, infinite loops, integer overflow in mid.",
    ),
    Q(
        "Given a grid of 1s (land) and 0s (water), how would you count the number of islands?",
        "Medium",
        [
            "dfs|bfs|depth-first|breadth-first",
            "visited|mark",
            "neighbors|adjacent",
            "o(m*n)|o(rows*cols)",
            "connected components",
        ],
        "Scan cells; on unvisited land start a DFS/BFS marking connected land visited and increment the count; O(rows*cols).",
    ),
    Q(
        "How would you detect whether a directed graph of task dependencies has a cycle, and produce a valid execution order?",
        "Hard",
        ["topological sort|topological", "in-degree|kahn", "dfs", "cycle", "queue"],
        "Use Kahn's algorithm with in-degrees and a queue (or DFS with colors); if not all nodes are processed there is a cycle; the processing order is a valid schedule.",
    ),
]

SYSTEM_DESIGN = [
    Q(
        "How would you design a URL shortener like bit.ly? Focus on the core components and how it scales.",
        "Medium",
        [
            "api|endpoints",
            "id generation|hash|base62",
            "database|key-value",
            "cache|caching",
            "redirect|301|302",
            "scale|read-heavy",
        ],
        "APIs for create/redirect, unique ID generation (base62 counter or hash with collision handling), key-value storage, caching hot links, read-heavy scaling with replicas, analytics async.",
        "How would you prevent two users from getting the same short code?",
    ),
    Q(
        "Design a notification service that sends email, SMS and push notifications for an app with millions of users.",
        "Hard",
        [
            "queue|message queue",
            "workers",
            "retries|retry",
            "rate limit|throttling",
            "templates|preferences",
            "idempotency|duplicates",
        ],
        "Producers enqueue events, workers per channel, user preferences and templates, retries with backoff and dead-letter queues, provider rate limits, idempotency to avoid duplicates, monitoring.",
    ),
    Q(
        "How would you design the backend for a hospital appointment booking system so two patients can't book the same slot?",
        "Medium",
        [
            "database|schema",
            "transaction|locking",
            "unique constraint",
            "concurrency|race condition",
            "notifications|reminders",
        ],
        "Model doctors, slots and appointments; enforce a unique constraint or transactional locking on the slot to prevent double booking; handle concurrency, cancellations and reminders.",
    ),
    Q(
        "Design a rate limiter for a public API.",
        "Hard",
        [
            "token bucket|leaky bucket|sliding window|fixed window",
            "per user|per key|per ip",
            "redis|shared store",
            "distributed",
            "429|headers",
        ],
        "Choose an algorithm (token bucket/sliding window), key by API key/user/IP, store counters in a shared store like Redis for multiple instances, return 429 with retry headers.",
    ),
    Q(
        "How would you design a simple chat application that supports real-time messaging?",
        "Medium",
        [
            "websocket|websockets",
            "message storage|database",
            "delivery|acknowledg",
            "online presence|presence",
            "scale|pub/sub|fan-out",
        ],
        "WebSockets for real-time delivery, persist messages, acknowledgements and ordering, presence, and pub/sub fan-out across server instances.",
    ),
    Q(
        "Design a resume screening service that parses uploaded resumes and matches them to job postings.",
        "Medium",
        ["upload|storage", "parsing|extraction", "queue|async", "matching|scoring", "search|index", "privacy|security"],
        "Upload to storage, asynchronous parsing workers, structured extraction, matching/scoring with an index, privacy controls and deletion.",
    ),
]

PROBLEM_SOLVING = [
    Q(
        "Users report that the app is intermittently slow, but you can't reproduce it locally. How do you approach this?",
        "Medium",
        [
            "reproduce|pattern",
            "logs|metrics|monitoring",
            "hypothesis|isolate",
            "database|external dependency",
            "fix|verify",
        ],
        "Look for patterns (time, endpoint, user), check logs/metrics/traces, isolate components (DB, external APIs), form and test hypotheses, fix and verify with metrics.",
        "Say the metrics show the slowness lines up with a nightly batch job. What would you do next?",
    ),
    Q(
        "A deployment just went out and the error rate jumped. What do you do in the first 15 minutes?",
        "Medium",
        [
            "rollback|roll back",
            "communicate|incident",
            "logs|dashboards|metrics",
            "impact|users affected",
            "root cause|postmortem",
        ],
        "Assess impact, communicate, roll back or disable the feature quickly, use logs/dashboards to confirm recovery, then find the root cause and write a blameless postmortem.",
    ),
    Q(
        "You're given a feature with vague requirements and a tight deadline. How do you proceed?",
        "Easy",
        [
            "clarify|questions",
            "stakeholders|product",
            "mvp|scope|prioritize",
            "assumptions|document",
            "iterate|feedback",
        ],
        "Clarify goals with stakeholders, define an MVP scope, document assumptions, deliver incrementally and get feedback early.",
    ),
    Q(
        "Your team's test suite takes 40 minutes and developers are skipping it. How would you fix this?",
        "Hard",
        ["measure|profile|slowest", "parallelize|parallel", "flaky", "test pyramid|unit tests|split", "ci|caching"],
        "Measure where time goes, fix or quarantine flaky tests, parallelize, rebalance toward fast unit tests, cache dependencies in CI, run subsets on PRs and full suite on merge.",
    ),
    Q(
        "You discover that a feature you shipped last month has been silently corrupting a small fraction of records. What do you do?",
        "Hard",
        [
            "stop|disable|hotfix",
            "assess|scope|impact",
            "communicate|escalate",
            "backfill|repair|restore",
            "prevent|tests|monitoring",
        ],
        "Stop the bleeding (disable/hotfix), quantify affected records, communicate transparently, repair or restore data, add tests and monitoring to prevent recurrence.",
    ),
    Q(
        "If you had to estimate how much storage a photo-sharing app needs per year, how would you reason about it?",
        "Medium",
        [
            "assumptions",
            "users|daily active",
            "photos per user|uploads",
            "size per photo|mb",
            "replication|thumbnails|growth",
        ],
        "State assumptions (users, uploads per day, average size), multiply out, add thumbnails, replication and growth; sanity-check the order of magnitude.",
    ),
]

BEHAVIORAL = [
    Q(
        "Tell me about a technically difficult problem you faced. How did you approach it, and what was the outcome?",
        "Medium",
        ["situation|context", "task|goal", "action|i did|i decided", "result|outcome", "learned|lesson"],
        "Use STAR: set the context briefly, explain your goal, focus on the specific actions you took and why, quantify the result, and share what you learned.",
        "What would you do differently if you faced the same problem again?",
    ),
    Q(
        "Tell me about a time you disagreed with a teammate or lead. How did you handle it?",
        "Medium",
        [
            "situation|context",
            "listen|understand",
            "data|evidence",
            "compromise|agreement|decision",
            "relationship|outcome",
        ],
        "STAR: describe the disagreement, how you listened and used evidence, how a decision was reached, and the outcome for the work and relationship.",
    ),
    Q(
        "Describe a failure or mistake you made. What happened, and what did you change afterwards?",
        "Medium",
        [
            "mistake|failure",
            "ownership|i was responsible|my fault",
            "impact",
            "fix|recovered",
            "changed|lesson|prevent",
        ],
        "Own the mistake, explain impact, how you fixed it, and the concrete change you made to prevent it recurring.",
    ),
    Q(
        "Tell me about a time you had to learn a new technology quickly to deliver something.",
        "Easy",
        [
            "context|deadline",
            "learning approach|documentation|tutorial|prototype",
            "applied|built",
            "result|delivered",
            "learned",
        ],
        "STAR with emphasis on how you learned (docs, small prototypes, asking experts), how you applied it and the outcome.",
    ),
    Q(
        "Tell me about a time you took ownership of something outside your direct responsibilities.",
        "Medium",
        ["situation|noticed", "initiative|took ownership|volunteered", "action", "result|impact", "stakeholders|team"],
        "Describe the gap you noticed, why you stepped in, what you did, and the measurable result.",
    ),
    Q(
        "Describe a situation where you had to work under a tight deadline. How did you prioritize?",
        "Easy",
        ["deadline", "prioritize|priorities", "scope|trade-off", "communicate|stakeholders", "result"],
        "Explain the constraint, how you prioritized and cut scope, communicated with stakeholders, and the result.",
    ),
    Q(
        "Tell me about feedback you received that was hard to hear. What did you do with it?",
        "Easy",
        ["feedback", "reaction|listened", "action|changed|improved", "result|outcome"],
        "Describe the feedback honestly, how you reacted, concrete changes you made, and evidence of improvement.",
    ),
    Q(
        "Tell me about a time you helped a teammate or mentored someone.",
        "Easy",
        ["situation", "helped|mentored|explained", "approach", "result|outcome"],
        "STAR: the teammate's challenge, how you helped (pairing, explaining, reviewing), and the outcome for them and the team.",
    ),
    Q(
        "Tell me about a time you had to make a decision without complete information.",
        "Hard",
        ["ambiguity|incomplete information", "assumptions|risks", "decision", "reversible|validate|monitor", "result"],
        "Explain the ambiguity, how you assessed risks and made assumptions explicit, the decision, how you validated it and the result.",
    ),
]

HR = [
    Q(
        "Why are you interested in this {role} role, and what are you looking for in your next position?",
        "Easy",
        ["motivation|interest", "role fit|skills", "growth|learning", "company|team|product"],
        "Connect your motivation and relevant skills to the role, and be specific about what you want to learn and contribute.",
    ),
    Q(
        "Where do you see yourself growing over the next two to three years?",
        "Easy",
        ["goals|growth", "skills", "realistic|specific", "contribution|impact"],
        "Give realistic, specific growth goals connected to the role and how you'd contribute along the way.",
    ),
    Q(
        "What kind of team environment helps you do your best work?",
        "Easy",
        ["collaboration|team", "communication", "feedback", "autonomy|ownership", "example"],
        "Describe concrete preferences (feedback, collaboration, ownership) with an example, while showing adaptability.",
    ),
    Q(
        "What do you consider your biggest strength and an area you're actively working to improve?",
        "Easy",
        ["strength", "example|evidence", "weakness|improve", "action|steps"],
        "Give one strength backed by evidence and a genuine area of improvement with concrete steps you're taking.",
    ),
    Q(
        "How do you handle multiple competing priorities?",
        "Easy",
        ["prioritize|priorities", "urgency|impact", "communicate", "tools|plan|list", "example"],
        "Explain your prioritization method (impact/urgency), how you communicate trade-offs, with a short example.",
    ),
    Q(
        "What does good code or good work quality mean to you?",
        "Easy",
        ["readable|maintainable", "tested|testing", "reviews|feedback", "simple|simplicity", "users|impact"],
        "Readable, tested, simple and maintainable work that solves the user's problem; mention reviews and documentation.",
    ),
]

SITUATIONAL = [
    Q(
        "Imagine a senior engineer asks you to ship a quick fix you believe is unsafe. What would you do?",
        "Medium",
        ["concerns|risk", "evidence|data", "alternatives|options", "respectful|communicate", "escalate|decision"],
        "Raise concrete risks with evidence, propose safer alternatives, communicate respectfully, and escalate or document the decision if needed.",
    ),
    Q(
        "You realize halfway through a sprint that your task will take twice as long as estimated. What do you do?",
        "Easy",
        ["communicate early|inform", "reason|why", "options|scope", "re-plan|prioritize", "learn|estimation"],
        "Communicate early with the reason, propose options (reduce scope, get help, move deadline), re-plan, and improve future estimates.",
    ),
    Q(
        "A customer reports a bug in a feature you built, but your tests all pass. How do you handle it?",
        "Medium",
        ["reproduce", "logs|information|details", "missing test|edge case", "fix", "communicate|customer"],
        "Gather details and reproduce, check logs, identify the untested edge case, fix with a regression test, and update the customer.",
    ),
]

INTRO = [
    "To start, could you walk me through your background and what's drawn you to {role} roles?",
    "Let's begin with a quick introduction. Tell me about yourself and the work you're most proud of so far.",
    "Could you give me a short overview of your background and the kind of {role} work you want to do next?",
]
INTRO_CONCEPTS = [
    "background|education|student|studying|degree|graduat|university|college|years",
    "experience|intern|project|built|worked|developed|role",
    "skills|technolog|stack|languages|tools",
    "motivation|interest|goal|passion|enjoy|looking for|want to",
]
INTRO_IDEAL = (
    "A 60-90 second narrative: current situation, one or two highlights with impact (projects or roles), "
    "the skills most relevant to this role, and why you're interested in it now."
)

PROJECT_TEMPLATES = [
    Q(
        "Walk me through {project}. What problem were you solving, who was it for, and what was your specific contribution?",
        "Easy",
        [
            "problem|goal",
            "users|who",
            "architecture|components|stack",
            "my contribution|i built|i designed|i implemented",
            "outcome|result",
        ],
        "State the problem and users, outline the architecture, be explicit about what you personally built, and end with the outcome or what you learned.",
        "Which part of {project} did you personally write, versus what came from teammates or libraries?",
    ),
    Q(
        "Why did you choose {techs} for {project}? What alternatives did you consider?",
        "Medium",
        [
            "requirements|needs",
            "alternative|instead|compared",
            "trade-off|tradeoff|downside",
            "familiarity|ecosystem|performance",
        ],
        "Tie choices to concrete requirements, name the alternatives you weighed, and acknowledge the trade-offs you accepted.",
    ),
    Q(
        "What was the hardest technical problem in {project}, and how did you solve it?",
        "Medium",
        [
            "problem|bug|challenge",
            "debug|investigat|root cause",
            "options|approach",
            "solution|fixed",
            "result|learned",
        ],
        "Describe one specific hard problem, how you diagnosed it, the options you considered, the fix, and the result.",
    ),
    Q(
        "If {project} suddenly had 100 times more users, what would break first, and how would you fix it?",
        "Hard",
        [
            "bottleneck",
            "database|queries|indexes",
            "caching|cache",
            "horizontal scaling|load balancer|replicas",
            "monitoring|measure",
        ],
        "Identify likely bottlenecks (database, synchronous calls, single server), propose fixes (indexes, caching, horizontal scaling, queues) and how you'd measure before changing.",
    ),
    Q(
        "How did you test {project}, and how did you know it actually worked for users?",
        "Medium",
        ["unit tests|tests", "manual testing|qa", "edge cases", "user feedback|users|pilot", "bugs|issues found"],
        "Describe your testing strategy (unit, integration, manual), edge cases, and real user feedback or metrics.",
    ),
    Q(
        "If you rebuilt {project} today, what would you do differently and why?",
        "Medium",
        ["mistake|limitation", "different approach|change", "why|reason", "trade-off", "learned"],
        "Name concrete limitations, what you'd change and why, showing reflection and growth.",
    ),
    Q(
        "In {project}, what happens if one of its dependencies — say the database or an external API — fails or becomes slow?",
        "Hard",
        [
            "failure|fails|down",
            "timeouts|timeout",
            "retries|retry",
            "error handling|graceful",
            "user experience|fallback",
        ],
        "Walk through failure modes, timeouts and retries with backoff, graceful degradation and what the user sees.",
    ),
]

EXPERIENCE_TEMPLATES = [
    Q(
        "Tell me about your role as {title} at {company}. What were you responsible for, and what are you most proud of there?",
        "Easy",
        ["responsibilities|role", "team|stakeholders", "specific example", "impact|result"],
        "Summarize scope and team, then go deep on one concrete accomplishment with measurable impact.",
    ),
    Q(
        "What was the most important thing you learned during your time at {company}, and how did it change how you work?",
        "Easy",
        ["lesson|learned", "example|situation", "change|apply", "impact"],
        "Name one lesson, the situation that taught it, and a concrete way it changed your approach.",
    ),
]

EDUCATION_TEMPLATES = [
    Q(
        "Which course or academic project from your {degree} best prepared you for a {role} role, and why?",
        "Easy",
        ["course|project", "skills|learned", "applied|example", "relevance|role"],
        "Pick one course or project, describe what you built or learned, and connect it explicitly to the role.",
    ),
]

CLAIM_TEMPLATES = {
    "metric": [
        Q(
            "I'd like to understand this result: “{claim}”. How did you measure it, and what was the baseline before your change?",
            "Medium",
            [
                "baseline|before",
                "measured|measurement|metric",
                "tool|benchmark|monitoring|profil",
                "after|result",
                "my contribution|i",
            ],
            "State the baseline, how and with what tool you measured, what exactly you changed, the after number, and caveats such as load conditions.",
        ),
        Q(
            "Walk me through how you achieved this: “{claim}”. What exactly did you change, and why did it work?",
            "Medium",
            ["root cause|problem", "change|implemented", "why|because", "verified|measured", "trade-off"],
            "Explain the original problem, the specific change, why it worked technically, how you verified it, and any trade-offs.",
        ),
    ],
    "architecture": [
        Q(
            "You described this: “{claim}”. How were the components divided, and how did they communicate?",
            "Hard",
            [
                "components|services|modules",
                "communication|api|http|queue",
                "data|database",
                "failure|errors",
                "why this design",
            ],
            "Describe the components and boundaries, how they communicate (sync APIs vs queues), data ownership, failure handling, and why the design fit the problem.",
        ),
    ],
    "leadership": [
        Q(
            "Tell me more about this: “{claim}”. How did you divide the work, and how did you handle disagreements in the team?",
            "Medium",
            [
                "divide|delegate|assigned",
                "communication|meetings|updates",
                "disagreement|conflict",
                "outcome|result",
                "my role",
            ],
            "Explain how you planned and delegated, how you kept everyone aligned, a concrete disagreement and how it was resolved, and the result.",
        ),
    ],
    "ownership": [
        Q(
            "About this: “{claim}”. Which parts did you personally design and build, and where did you get help?",
            "Medium",
            ["my contribution|i built|i designed", "help|team|mentor", "decisions", "challenges"],
            "Be precise about what you personally designed and built, decisions you made, and where you relied on others.",
        ),
    ],
    "scale": [
        Q(
            "About this: “{claim}”. What load did it actually handle, and what would break first at ten times that?",
            "Hard",
            ["load|traffic|users", "measured|metrics", "bottleneck", "scaling|cache|replicas", "monitoring"],
            "Quantify real load and how it was measured, identify the first bottleneck at 10x, and how you'd address it.",
        ),
    ],
}

JD_GAP_TEMPLATE = Q(
    "This role relies on {skill}. Have you worked with it or something similar, and how would you get productive with it in your first few weeks?",
    "Easy",
    [
        "related experience|similar|transferable",
        "learning plan|documentation|course|build",
        "first project|small task",
        "ask|mentor|team",
    ],
    "Be honest about your level, connect transferable experience, and give a concrete learning plan (docs, a small project, pairing) with a timeline.",
)

CLOSING_LINES = [
    "That brings us to the end of the interview. Thank you for your time and thoughtful answers — I'll put together your feedback now.",
    "That's all the questions I have for today. Thanks for walking me through your experience; your report will be ready shortly.",
]
