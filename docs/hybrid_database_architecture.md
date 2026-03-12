# SignGlove V3 Hybrid Database Architecture

This document outlines the "Bond" between **PostgreSQL** and **MongoDB** in the SignGlove V3 system.

## 1. The Strategy: Separation of Concerns

To achieve both high-integrity management and high-volume performance, we split our data:

*   **PostgreSQL (Relational)**: Handles high-integrity, structured data such as User Auth, Dataset Metadata, and Model Registry. It uses `JSONB` for flexible but queried model configurations.
*   **MongoDB (Document/NoSQL)**: Handles high-velocity, unstructured streams of ML sensor data and real-time prediction logs.

---

## 2. Database Relationship Diagram (Mermaid)

The "Bond" is established via unique identifiers (UUIDs) generated in PostgreSQL and referenced in MongoDB documents.

```mermaid
erDiagram
    %% PostgreSQL Side (High Integrity)
    USER ||--o{ DATASET : "owns"
    DATASET ||--o{ MODEL : "trains"
    
    USER {
        uuid id PK
        string email UK
        string hashed_password
        string role
        timestamp created_at
    }

    DATASET {
        uuid id PK
        string name
        string storage_path
        string modality
        jsonb metadata_json "Schema & Stats"
        uuid owner_id FK
    }

    MODEL {
        uuid id PK
        string name
        string artifact_path
        float accuracy
        jsonb config_json "Input Spec"
        uuid training_dataset_id FK
    }

    %% MongoDB Side (High Performance)
    DATASET ||--o{ SENSOR_DATA : "linked_by_id"
    MODEL ||--o{ PREDICTION : "generated_by_id"

    SENSOR_DATA {
        string session_id "Dataset UUID"
        int timestamp_ms
        double_array values
        string source
    }

    PREDICTION {
        string model_id "Model UUID"
        string label
        float confidence
        int latency_ms
    }
```

---

## 3. The "Bond" Mechanism

### Relational Integrity (PostgreSQL)
We use **SQLAlchemy** with **asyncpg** to manage the lifecycle of our core entities. 
- **Users**: Strict unique constraints on email.
- **Datasets/Models**: Foreign key constraints ensure that artifacts are never "orphaned." If a user is deleted, their metadata remains or cascades according to policy.

### Performance Data (MongoDB)
We use the **Motor** driver for asynchronous non-blocking I/O.
- **Sensor Data**: Linked to a `Dataset.id` via the `session_id` field.
- **Indexing**: MongoDB is indexed on `session_id` and `timestamp_ms` to ensure sub-millisecond retrieval of temporal sequences, as verified in our harsh tests.

---

## 4. Key Architectural Benefits

1.  **Immutability**: Following the "Artifact Chaos" prevention strategy, every new model training run creates a new entry in PostgreSQL and a new storage directory, preventing race conditions.
2.  **Scalability**: We can scale PostgreSQL vertically for complex queries and MongoDB horizontally (sharding) for millions of sensor frames.
3.  **JSONB Flexibility**: PostgreSQL `JSONB` columns allow us to store different metadata schemas for `CV`, `Sensor`, and `Fusion` datasets without performing costly SQL migrations for every new ML experiment.
4.  **Async-First**: Both database layers are fully asynchronous, ensuring the API remains responsive (sub-10ms) even under heavy load.
