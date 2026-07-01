### OCR based, GDPR compliant receipts processing tool

Idea behind this project is to use a fusion of propietary but RODO compliant OCR solutions & local GPU powered image-to-text model.

From architecture side, k3s with embedded etcd will be good fit

work in progress, stay tuned

```mermaid
---
config:
    look: handDrawn
---
flowchart LR
    n1["file"] --> n2["Gateway with choosed model"]
    n5 --> n7["Unified format (models.py)"]
    n4 --> n7
    n6 --> n7
    n7 --> n8["Response JSON/CSV"]

    n1@{ shape: rounded}
    n2@{ shape: rounded}
    n4@{ shape: rect}
    n7@{ shape: rounded}

	n2 --- n5["P1: Google DocAI (EU)"]
	n2 --- n4@{ label: "P2: Mistral OCR" }
	n2 --- n6["P3: local gpu"]
```

