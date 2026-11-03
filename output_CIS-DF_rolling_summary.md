# Document Summary & Topic Overview

- **Serverless Discovery**  
  - Pattern‑based, no host scanning  
  - Enables rapid CI discovery without network scans  

- **Duplicate CI Handling**  
  - Identification via IRE rules and the **Duplicate of** field  
  - Remediation Wizard guides manual merge/delete actions  
  - De‑Duplication Templates enable bulk automated merging/deleting  

- **CMDB Data Manager**  
  - Lifecycle policies: retire, archive, delete  
  - Data certification and attestation validate infrastructure/applications  
  - Requires active lifecycle rules per CI class  

- **CMDB Insight & Data Foundations Dashboards**  
  - Visibility into data quality and CSDM alignment  
  - Monitors policy compliance and offers playbooks  
  - Remediation playbooks provide context and guidance  

- **CMDB Query Builder**  
  - Drag‑and‑drop visual query construction  
  - Supports AND/OR logic across CMDB and non‑CMDB tables  
  - Requires understanding of the data model and CI relationships  

- **Unified Map**  
  - Interactive visual map of CIs and dependencies  
  - Accessible from CMDB Workspace  
  - Combines Application Service and Dependency View  

- **Intelligent Search**  
  - AI‑powered natural language queries  
  - Reduces need for deep technical knowledge  
  - Supports advanced filtering  

- **CI Class Manager**  
  - Group‑value precedence via technical service offering overrides; identification rules (unique attributes, allow nulls, parent fallback)  
  - Dependent relationships: Hosting (direct) vs Containment (hierarchical), impact analysis, lifecycle management  
  - Reconciliation, Data Refresh, and Suggested relationships: source priority, conflict resolution, refresh thresholds, logical guidance (e.g., Provides Power for, Runs on)  

- **Principal Class**  
  - Designates CI class for streamlined ITSM references  
  - Filters Configuration Item field in incidents, problems, changes  
  - Reduces clutter and improves efficiency  

- **Life Cycle Management**  
  - CSDM Life Cycle fields standardize status; legacy fields remain  
  - ServiceNow auto‑syncs CI, Asset, IBI via mapping tables  
  - Legacy ↔ CSDM mapping table for one‑time sync and discrepancy report  

- **Governance & Health**  
  - Health Dashboard tracks Correctness, Completeness, Compliance; Health Inclusion Rules filter CI classes and