# CMDB and CSDM

## Common Service Data Model (CSDM)
The Common Service Data Model is a standard set of service‑related definitions that span the ServiceNow product portfolio and the Now Platform. It enables true service‑level reporting and provides prescriptive guidance on service modeling within the CMDB.

## Configuration Item (CI)
Physical and logical components of an infrastructure that must be managed to deliver a product or service. Examples include network devices, servers, applications, delivery trucks, or services that are currently or soon will be under configuration management.

## Attribute
Information that further describes a CI, such as a name, serial number, manufacturer, or operating system.

## Relationship Type
Defines how configuration items relate to one another. For example, a web application might read data from a specific database, which in turn depends on underlying hardware.

## Class
Represents a table that contains and describes a specific type or group of CIs that share common attributes. Examples include Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, Animal, etc.

## Configuration Management Database (CMDB)
A database that stores configuration records throughout their lifecycle. The Configuration Management System maintains one or more CMDBs, each of which stores attributes of CIs and their relationships with other CIs.

## Base Table
The core `cmdb_ci` table that stores the basic attributes of all CIs. All configuration item classes extend from this table, including all hardware and applications.

## CI Reclassification
A CI whose class has been upgraded, downgraded, or switched. For example, a server record upgraded from the `cmdb_ci_server` class to the `cmdb_ci_win_server` class.

## Parent and Child Class
A table that extends another table is called a child class, and the table it extends is the parent class. A table can be both a parent and child class, extending and providing extensions for other tables. For example, the Server table extends the Computer table, and the Windows Server table extends the Server table, making the Server table both a parent and child class.

## Asset vs. CI
On the Now platform, creating a hardware asset automatically creates a corresponding CI, and vice versa. The asset and the CI are connected throughout the CI/Asset lifecycle.

### Asset
- Often starts during the procurement process, but may be created when a discovery tool finds the CI for the first time.
- Part of the financial lifecycle.

### Configuration Item (CI)
- Often starts when a discovery tool finds the CI for the first time, but may be created during the procurement process.
- Part of the technical operations.

## Application Service
*(Content to be added)*

## Application Service

A set of interconnected applications and hosts that are configured to offer a service to the organization. Application services can be internal, such as an organization email system, or customer‑facing, such as an organization website.

### Application
Applications that comprise an application service are stored in the CMDB as configuration items (CIs). The various applications and the relationships between them that make up an application service are captured in the CMDB (e.g., Tomcat, Apache, Microsoft SQL, Oracle, IIS).

### DevOps
DevOps combines developers who build applications with the operations groups that deploy and maintain them within an enterprise. In a DevOps environment, these two groups work together as a single team to accelerate and improve service delivery.

### Principal Class
Principal classes can be configured to limit the CI classes that appear in the Configuration Item fields on incident, problem, and change records.

### Logical CI
Logical CIs do not occupy physical space; they perform specific functions that require physical components to operate. Examples include Service Offering, Service, and Business Application, which are manually entered into the CMDB.

#### Examples
1️⃣ **Business Application**  
   *Logical CI*: “Microsoft Teams” (the collaboration/chat app used by employees)  
   *Physical CIs it depends on*:  
   - Cloud servers hosting Teams  
   - Network infrastructure (routers, switches)  
   - Databases storing user info and messages  

2️⃣ **Service**  
   *Logical CI*: “Corporate Email Service”  
   *Physical CIs it depends on*:  
   - Exchange Server or Office 365 backend  
   - Mail servers  
   - Storage for email data  
   - Network connections for email delivery  

3️⃣ **Service Offering**  
   *Logical CI*: “VPN Access for Remote Employees”  
   *Physical CIs it depends on*:  
   - VPN servers  
   - Firewalls  
   - Network links to the corporate office  

4️⃣ **Other Examples**  
   *Logical CI*: “HR Payroll System” – depends on payroll application servers, database servers, authentication servers.  
   *Logical CI*: “Customer‑Facing Website” – depends on web servers, application servers, load balancers, content delivery network.

💡 **Tip**  
A simple way to think of it:  
- **Logical CI** = What the business sees / uses  
- **Physical CI** = What actually runs it behind the scenes  

### Foundation Data
Foundation data is not part of the CMDB itself but is referenced in CI records. Selecting the appropriate CI classes, levels, attributes, and relationships is one of the most important and challenging aspects of CMDB design. During a CMDB health check, ServiceNow examines the number of custom classes and attributes created and assesses whether these custom attributes are established at the correct level. ServiceNow provides a free store application called **CMDB CI Class Models** that can be installed on a ServiceNow instance to obtain a wide range of additional classes that are not provided in a base instance.

### Automated Discovery Tools
ServiceNow offers several automated discovery tools, including:
- **ServiceNow Discovery**  
- **Service Mapping**  
- **Agent Client Collector**

### Configuration and Asset Management Lifecycles
An asset becomes a CI when it is deployed and remains a CI throughout its lifecycle until it is returned to stock or disposed of. Configuration Management and IT Asset Management are distinct yet complementary practices.

### Change Control Board (CCB)
Form a **Configuration Control Board (CCB)**. The CCB is a team that ensures your CMDB delivers continuous value. This team sets direction, makes decisions on what is needed to support your organization’s strategic initiatives, and determines whether the CMDB is ready for utilization.



### Automated Discovery Tools

#### Discovery Configuration and Best Practices

Pattern-based and does not rely on traditional host discovery.

✔ **Key takeaway:** All are forms of horizontal Discovery, each targeting different environments and use cases.

##### Limiting Discovery Data
- Improves data accuracy  
- Avoids populating the CMDB with low‑priority or irrelevant data  
- Establishes a strong foundation with high‑quality CIs  
- Prevents CMDB data overload  
- Reduces clutter caused by unnecessary Discovery results  
- Keeps the CMDB clean and maintainable  
- Faster initial deployment  
  - Fewer devices scanned → quicker Discovery cycles  
  - Enables a usable CMDB early, with gradual expansion later  
- Simplifies CMDB management  
  - Focuses on key CI classes (e.g., servers, critical applications)  
  - Ensures data is immediately relevant to business needs  
- Better stakeholder buy‑in  
  - Quick wins with accurate data build trust  
  - Encourages support for broader Discovery adoption later  

✔ **Key takeaway:** Start small, discover what matters first, then expand Discovery incrementally.

##### Discovery Ranges
Discovery ranges define which IP addresses ServiceNow Discovery scans.  
You can include or exclude specific IP ranges in a Discovery schedule.

###### Broad Ranges (Subnets)
Example:
- 192.168.0.0/24  
- 10.11.128.192/26  

Includes network and broadcast addresses.  
Scans a large number of IPs, which may cause:
- Data overload  
- Redundant or irrelevant CIs  
- Discovery errors  

Not recommended during initial implementation.  
Best practice: Do not exceed /16 (~65,000 IPs); split into smaller ranges if needed.

###### Limited Ranges (Preferred Initially)
Example:
- 192.168.0.1 – 192.168.0.254

### Operational accountability
✔ Key takeaway: Discovery populates technical CI data; CMDB admins must enrich CIs with non‑discoverable ownership and group information.

### Service Mapping (Top‑Down / ML‑Powered, Tag‑based discovery)
- Builds end‑to‑end service maps showing how business services are supported by IT components.
- Dynamically updates relationships as changes occur.
- **License:** Paid (ITOM Visibility).
- **Note:** Follow CSDM guidelines, define service owners, and relate services to business applications.
- **Business Value:**
  - Bridges the gap between IT Operations and business users.
  - Aligns IT service delivery with business outcomes, not just infrastructure.
  - Supports ITSM processes: Incident, Problem, and Change Management.
- **Key Concepts:**
  - **Application Service:** Logical representation of a deployed system, application, or product stack.
  - **Operational CI** used in ITSM/ITOM practices.
  - Can be environment‑specific (Dev, Test, QA, Prod) or region‑specific (AMS, EMEA, APJ).
  - Stored in `cmdb_ci_service_auto` or sub‑classes.
  - **Service Map:** Shows which CIs support a service, including applications, servers, middleware, and networks.
  - Helps identify service impact when components fail.
- **Types of Application Services**
  - **Top‑Down Mapping**
    - **Pattern‑Based:**
      - Best for: Mission‑critical apps.
      - Level: Surgical/Process‑to‑process.
      - Key: Most Granular.
    - **ML Connection Suggestions:**
      - Best for: Homegrown & custom COTS.
      - Level: Traffic‑based/Fingerprinting.
      - Key: Fastest Time‑to‑Value.
    - *Note:* These two can be used together or individually.
  - **Tag‑Based Mapping**
    - Best for: Cloud‑native, Containers, and VMs.
    - Effort: Medium touch (requires defining tag categories/families).
    - Key: Visualizes resource stacks across cloud infrastructure.
  - **Dynamic CI Group**
    - Best for: Small application services.
    - Mechanism: Uses CI list filters or CMDB queries.
    - Effort: High touch (requires manual query building).
    - Key: No License Required.
- **Integration with CSDM**
  - Supports Common Service Data Model (CSDM) by automating service and dependency modeling.
  - **Benefits include:**
    - Accurate service modeling
    - Enhanced CMDB data quality
    - Dependency management for impact analysis and operational support
- **Benefits:**
  - Enhanced visibility of IT services and dependencies
  - Faster root‑cause analysis for incidents and problems
  - Proactive, low‑risk change management
  - Improved compliance and governance through clear documentation
✔ Key takeaway: Service Mapping automates discovery and mapping of services and their dependencies, enabling IT teams

## Discovery and Service Mapping Patterns

### Non‑CMDB Tables Supported by Default
The system property `glide.identification_engine.non_cmdb_tables` lists the only tables that IH‑ETL and IRE can work with. Identification rules (CI identifiers and identifier entries) must be created for these tables.

| Table | Description |
|-------|-------------|
| `cmn_location` | Location |
| `cmn_department` | Department |
| `cmn_cost_center` | Cost Center |
| `cmn_building` | Building |
| `sys_user` | User |
| `sys_user_group` | Group |

### Discovery and Service Mapping Patterns Application
The Discovery and Service Mapping Patterns application is a ServiceNow Store app. New discovery patterns are released regularly through the ServiceNow Store, independent of major platform releases, allowing customers to receive updated patterns without a full ServiceNow upgrade.

### Service Graph Connectors
Pre‑built integrations that sync data from external systems (e.g., Azure, Intune, MS SCCM, Jamf, AWS) to ensure CMDB data consistency across tools. They can automatically synchronize and update the CMDB in real‑time or on a scheduled basis, reducing manual data entry and improving efficiency.

| Connector | License | Notes |
|-----------|---------|-------|
| Azure | Paid | Requires credentials |
| Intune | Paid | Requires credentials |
| MS SCCM | Free | Requires credentials |
| Jamf | Paid | Requires credentials |
| AWS | Paid | Requires credentials |

### Import Sets & Transform Maps (Legacy Method)
- Imports data from files, databases, or APIs into staging tables.  
- Supports field mapping and transform scripts.  
- **License:** No.  
- **Note:** Does not use IRE by default, risking duplicates—recommended to enforce IRE via transform scripts.

#### Utilizing IRE During a CMDB Import
The Identification and Reconciliation Engine (IRE) centrally identifies and reconciles CI data from multiple sources, including manual imports.

- Identification rules are defined per CI class and consist of identifier entries (unique attribute sets with priorities) and related entries.  
- By default, IRE is not used during imports. It must be explicitly enabled using a custom `onBefore` script in the transform map.  
- The `CMDBTransformUtil` API sends import set data to the IRE for identification before insert/update.  
- IRE determines whether a CI is new or existing:  
  - **New CI** → Insert into CMDB  
  - **Existing CI** → Update the existing record  
- When using `CMDBTransformUtil`, coalesce settings are ignored and are not required.

### Data Manager
Data Manager enables periodic certification and auditing of CMDB data to ensure accuracy and completeness. It uses scheduled certification policies that assign verification tasks to responsible users or groups.

#### Auto‑Populate Group Fields
| Priority | Method | Description | Applies To |
|----------|--------|-------------|------------|
| 2 | CI Class Manager | Set Managed By Group at the CI class level; applies to all CIs in the class not linked to a Technology Management Offering. | All CIs in the class |
| 1 | Technology Management Offering | Set Managed By, Support, and Change Groups at the offering level; applies to associated CIs and overrides CI Class Manager values. | CIs associated with the offering |

Technology Management Offerings use dynamic CI groups behind the scenes to apply group values to their CIs.

#### CI Attribute Population Using Technology Management Offering
1. Create a CMDB Group  
2. Create a Dynamic CI Group  
3. Create a Technology Management Service  
4. Create a Technology Management Offering  
5. Associate Dynamic CI Group to the Offering  

#### Automatic Group Synchronization
- System Business Rule (CSDM – Sync Group Attributes) syncs group values.  
- Service Builder is an alternative UI to achieve the same result, but it needs to be installed first from the ServiceNow store application.

# Management Tools Overview

## CMDB Workspace

## CMDB Governance

## CMDB Health Dashboard

The CMDB Health Dashboard monitors overall CMDB data quality through scorecards for **Completeness**, **Correctness**, and **Compliance**. It highlights the top CI classes impacting health and allows drill‑down analysis.  
*Scheduled jobs must be manually activated for scorecards to populate.*

### Purpose
Provides a quick view of the overall quality of CMDB data using three key scorecards.

### Completeness
Measures whether CIs have all required and recommended fields populated, including non‑discoverable data (e.g., ownership, support group).

- **Exam Tip:** Missing essential data lowers completeness. Uses Recommended and Required metrics.  
- ServiceNow does not provide predefined required or recommended CI attributes in the CMDB. These must be defined by the CMDB administrator and relevant stakeholders based on process requirements.

To prevent integrations (including Discovery and IRE) from failing due to missing mandatory CMDB attributes, ServiceNow provides two ways to override the default behavior:

| Method | Steps |
|--------|-------|
| **Via CMDB Properties UI** | 1. Navigate to **Configuration > CMDB Properties > Identification/Reconciliation Properties**.<br>2. Find “Enforce the requirement that required attributes cannot be null during identification and reconciliation”.<br>3. Deselect the checkbox (set to false) and save. |
| **Via System Properties** (`sys_properties.list`) | 1. Locate the property `glide.required.attribute.enabled`.<br>2. Set its value to `false`. |

> **Exam takeaway:** Both methods disable enforcement of required attributes during IRE identification and reconciliation, allowing integrations to proceed even when mandatory fields are missing.

### Compliance
Shows how well CIs adhere to defined standards and audit policies. Uses the Audit metric.

- **Exam Tip:** Evaluates alignment with desired state configurations.  
- Compliance audits verify that CIs meet defined standards or policies. Typical examples include ensuring antivirus is installed, systems are patched to required levels, and mandatory ownership fields (such as Support Group and Managed by Group) are populated.

A common use case is system upgrades, where compliance audits identify servers that do not meet minimum hardware requirements (disk space, RAM, CPU) needed for the next upgrade. The Compliance Scorecard highlights non‑compliant CIs so issues can be addressed before the upgrade.

#### What Compliance Is Based On
Audits compare actual CI values vs expected values. Expected values are defined via:

- Certification Templates
- Scripted Audits

#### Common Audit Examples
- Antivirus installed on all workstations  
- Linux servers on latest patch  
- Production servers have Support Group and Managed by Group  
- Hardware readiness for OS upgrades (RAM, disk, CPU)

#### Key Rule (Very Important for Exam ❗)
✅ Only these audit types appear in the CMDB Health Dashboard Compliance Scorecard:

- Desired State audits  
- Scripted audits  

🚫 NOT included in the scorecard:

- Compliance  
- Compliance Architecture  

#### Compliance Scorecard Configuration (4 Required Components)

1. **Certification Filter**  
   - Defines scope of the audit (which CIs).  
   - Based on CI class and conditions.  
   - Examples:  
     - All Windows Computers  
     - All UNIX servers in a datacenter  
   - **Navigation:** `CI Class Manager → Health → Compliance` or `Compliance > Filters`

2. **Certification Template**  
   - Defines conditions to pass the audit.  
   - Can check:  
     - Attributes  
     - Relationships  
     - Reference fields  
   - Must reference a Certification Filter.  
   - Audit type must be **Desired State**.  
   - **Navigation:** `CI Class Manager → Health → Compliance` or `Compliance > Templates`

3. **Audit**  
   - Executes the comparison.  

4. **Audit Execution** (implied)  
   - Runs the audit against the defined filter and template, producing the compliance results displayed in the dashboard.  

> **Navigation:** `Compliance > Audits`

---

##### Filtered CIs vs Template Conditions
- Can be scheduled  
- Create remediation tasks and assign them to a user or a group to work on them  
- Uses the standard ServiceNow scheduler  

**Navigation:** `CI Class Manager → Health → Compliance` or `Compliance > Audits`

##### 4️⃣ Compliance Score Calculation Job
Calculates the Compliance KPI after audits run.

- **Scheduled Job:** CMDB Health Dashboard – Compliance Score Calculation  
- **Navigation:** `Configuration > Health Preferences > Scheduled Jobs`  
- Must be:  
  - Activated  
  - Run by a user with the admin role  
- **Status table:** `cmdb_health_metric_status`  
- ⚠️ If run by a non‑admin → inaccurate results  

##### Scripted Audits
Used when templates are too restrictive; logic is defined in a script.

- Still use a **Certification Filter** and are included in the Compliance Scorecard  
- Cannot be created via CI Class Manager  
- **Navigation:** `Compliance > Desired State > Scripted Audits > Audits`

**Base system includes sample:** `Data Center Zone Usage`

**Desired State vs Data Manager** (Exam Favorite 💡)

**CMDB Health Desired State Audits**  
- Automatic  
- Ensures fields are:  
  - Present  
  - Configured correctly  
- **Example:** Server has an owner and support group  

**Data Manager Certification Policies**  
- Manual verification  
- Used when data cannot be discovered automatically  
- Generates certification tasks/checklists  
- **Example:** Confirm Joe Smith is the correct owner of ServerXYZ  

👉 They serve different purposes and are NOT the same  

##### Correctness
Checks accuracy of CMDB data, including duplicates, outdated CIs, and proper relationships. Uses Duplicate, Orphan, and Staleness metrics.

- **Exam Tip:** A CI passes correctness only if it meets all defined metrics.  
- **Score Calculation:** Overall percentage = % of CIs that pass all metrics, not an average of individual metrics.  
  - **Example:** Metrics: 93 %, 100 %, 96 % → overall = 89 % (because only 89 % of CIs met all metrics).  

##### Duplicate CIs Definition
Occurs when multiple CMDB records exist for a single real‑world CI.

**Key Points**  
- Evaluated using predefined identification rules.  
- Only independent CIs are evaluated (e.g., hardware, servers – not applications).  

**Duplicates can be detected

##### Duplicate CIs Definition

Servers discovered daily → staleness = 7 days  

**Why It Matters**  
Prevents use of non‑existent or outdated CIs.  
Critical for lifecycle management and downstream processes.  

**Configuration & Governance**  
- **CI Class Manager** – used to configure Correctness Scorecard rules.  
  Supports:  
  - Duplicate identification  
  - Orphan rules  
  - Staleness rules by class  

**Exam Takeaways (High‑Probability Questions)**  
- ✅ Correctness Scorecard measures Duplicate, Orphan, and Stale CIs  
- ✅ Duplicate metric applies only to independent CIs  
- ✅ Oldest CI = primary, newer ones = duplicates  
- ✅ No default orphan rules → must be configured manually  
- ✅ Base staleness rule = 60 days at `cmdb_ci`  
- ✅ `sys_updated_on` drives staleness calculation  
- ✅ Metrics roll up into the CMDB Health Dashboard  

**Manage & Remediate Duplicate CIs — Exam Notes**  

**What Are Duplicate CIs?**  
Duplicate CIs = two or more CMDB records representing the same real‑world item.  
They negatively impact:  
- Incident, Change, and Problem Management  
- Reporting & compliance  
- Trust in CMDB data  

**Common Causes of Duplicate CIs**  
- Discovery tools (multiple tools discovering the same CI differently)  
- Import Sets without proper identification rules  
- Third‑party integrations (REST/SOAP) without IRE logic  
- Manual CI creation (poor governance, no naming standards)  
- Incorrect or missing Identification Rules  
- Lack of CMDB governance  

**How ServiceNow Determines Duplicates**  
Duplicates are detected by the Identification and Reconciliation Engine (IRE).  
IRE uses:  
- **Identification Rules** → determine what uniquely identifies a CI  
- **Reconciliation Rules** → determine which data source wins  

If multiple CIs match identification rules, a de‑duplication task is created and visible in CMDB Workspace.  

⚠️ **Important Exam Gotcha**  
If duplicate CIs already have a Discovery Source populated, the CMDB Health Dashboard Correctness Scorecard will NOT flag them.  
Once rediscovered and reprocessed by IRE, they will be flagged and a de‑duplication task is generated.  
Duplicate CIs are only flagged by CMDB Health after they are processed by IRE – existing duplicates with a populated Discovery Source are ignored until rediscovery happens.  

**Discovery Behavior with Duplicates**  
When duplicates are found during Discovery:  
- Oldest CI (by creation date) is updated  
- Others are marked as duplicates  

**Key Field Change (Important Update 🚨)**  
- **Old**: Discovery Source field was used to indicate duplicates  
- **New**: Duplicate of field  
  - Reason: Preserve the Discovery Source with the last discovery tool  
  - Functionality remains the same  

**De‑duplication Tasks**  
Created automatically when IRE detects duplicates.  
Allow admins to:  
- Review duplicate CIs  
- Decide how to remediate them  

Access:  
- Legacy: De‑duplication Tasks module  
- Current: CMDB Workspace  

**Duplicate CI Remediator**  
Wizard launched from a de‑duplication task.  
Admin can:  
- Select Main CI  
- Merge attributes  
- Maintain audit trail  

Supports:  
- Merge  
- Retain one CI  
- Eliminate duplicates  

**De‑duplication Templates**  
Used for bulk remediation:  
- Pre‑configured remediation logic  
- Applied per CI class or in bulk  
- Managed from De‑duplication Dashboard in CMDB Workspace  
Templates can be organized into libraries and executed on multiple de‑duplication tasks at once.  

**System Properties for Duplicate Handling**  
Memorize these 🔑:  
- **Behavior**:  
  - If duplicates < threshold: Oldest CI is updated, others get Duplicate of populated  
  - IRE ignores CIs where Duplicate of is populated  

**Now Assist for CMDB (AI‑based)**  
Know what it does, not how to configure:  
- Uses Generative AI

##### Duplicate CIs Definition  

**Automates**  
- Duplicate CI detection  
- CI summarization  
- Suggested remediation steps  

**Works with**  
- De‑duplication templates  
- CMDB Workspace  

**Goal**  
- Reduce manual effort  
- Improve CMDB accuracy & governance  

---

## Why Handling Duplicates Matters (Exam Framing)

- Ensures CMDB as a Single Source of Truth  
- Improves:  
  - IT operations  
  - Reporting & compliance  
  - Decision‑making  

**One‑Line Exam Summary**  
Duplicate CIs are identified by the IRE using identification rules, managed via de‑duplication tasks in CMDB Workspace, remediated using the Duplicate CI Remediator or de‑duplication templates, and flagged using the *Duplicate of* field—not *Discovery Source*.

---

## CI Reclassification & Restriction Rules — Exam Notes (Concise)

### CI Reclassification — Core Concepts  
- **Reclassification** = moving a CI to another class during IRE identification.  
- Happens when CI data is placed in the wrong CMDB class.  

**Types**  
- **Upgrade** → more specific (e.g., *Server* → *Windows Server*)  
- **Downgrade** → less specific (e.g., *Windows Server* → *Server*)  
- **Switch** → different branch (e.g., *Linux Server* ↔ *Windows Server*)  

**Default behavior**: automatic reclassification is enabled.

### Which reclassification behaviors might cause CI attributes and their data to be excluded during the reclassification process?  
*(Choose two)*  
- Upgrade  
- Downgrade  
- Promotion  
- Switch  

### Which results in a reclassification task being generated?  
- When `glide.class.downgrade.enabled` is set to **true** and during discovery a Windows server is classified as a Linux server.  
- A reclassification task is generated only if the relevant reclassification property is set to **false**.  
  - Example: when a Server record is reclassified as a Windows server (an upgrade), and `glide.class.upgrade.enabled` is set to **false**, a reclassification task is triggered.

---

## Automatic vs Manual Reclassification  

| Mode | Behavior | Risk / Outcome |
|------|----------|----------------|
| **Automatic** (default) | CI is reclassified immediately | Data loss during downgrade or switch |
| **Manual** | CI is not reclassified | Reclassification task is created for admin review |

### Base Reclassification System Properties  
- `glide.class.upgrade.enabled`  
- `glide.class.downgrade.enabled`  
- `glide.class.switch.enabled`  

Setting any of these to **false** prevents that reclassification type and creates a reclassification task.

### Granular Control (Advanced IRE Properties)  
These override legacy behavior:  
- `glide.identification_engine.update_without_upgrade_enabled`  
- `glide.identification_engine.update_without_downgrade_enabled`  
- `glide.identification_engine.update_without_switch_enabled`  

**Behavior when set to true**:  
- CI attributes are updated  
- CI class is **NOT** changed  

⚠️ These properties take precedence over `glide.class.*`.

---

## Key Rule to Memorize  
### Reclassification Restriction Rules  

**Purpose**  
- Class‑level control  
- Prevent specific downgrades or switches  
- Still allow attribute updates  

**Scope**  
- Applies only to reclassification  
- Does not block attribute updates  

**Location**  
- `cmdb_ire_reclassification_restriction.list`

### Restriction Rule Behavior  
- **Key fields**:  
  - **Type**: Downgrade or Switch  
  - **Source / Target table**  
  - **Inheritance flags**:  
    - `true` → includes extended classes  
    - `false` → exact class only  

**Exam Pattern: Inheritance Logic**  
- Source inheritance = **true** → rule applies to all child classes  
- Target inheritance = **false** → rule applies only to exact target class  

---

## Review Questions — Correct Answers  

### Question 1  
**Config**  
```text
glide.class.downgrade.enabled = true
glide.identification_engine.update_without_downgrade_enabled = true
```  
**Answer**  
- Windows Server **IS NOT** allowed to be downgraded  
- Windows Server CI attributes **CAN** be updated  

### Question 2  
**Config**  
```text
glide.class.downgrade.enabled = true
glide.identification_engine.update_without_downgrade_enabled = false
```  
**Restriction Rule**  
- **Type**: Downgrade  
- **Source**: Server (inheritance = true)  
- **Target**: Computer (inheritance = false)  

**Answer**  
- Windows Server **IS NOT** allowed to be downgraded to Computer  
- Windows Server CI attributes **CAN** be updated  

### Question 3  
**Config**  
Same restriction rule as Q2  
**CI**: IP Router → Network Gear  

*(Answer not provided in the raw text; students should apply the same logic as Q2.)*

### Question 3

**Answer**  
- IP Router **IS** allowed to be downgraded  
- IP Router CI attributes **CAN** be updated  
(Restriction applies only to Server and its child classes)

## CMDB Health Dashboard

### One‑Line Memory Hook
- CMDB Health = Completeness (fields), Compliance (standards), Correctness (accuracy), overall % = CIs passing all metrics.

### Health Inclusion Rules
- **Purpose**: Define which CI classes are evaluated by the CMDB Health Dashboard (Correctness, Completeness, Compliance).  
- **Why needed**: Discovery tools can populate large volumes of CIs; not all are owned or managed by the organization.  
- **Best practice**: Include only CI classes your organization is responsible for to ensure meaningful and performant health metrics.

#### Key Capabilities
- Selective Class Tracking: Limit health calculations to relevant CI classes.  
- Metric‑Level Control: Apply rules to specific metrics (e.g., Correctness only).  
- Customizable Scope: Include or exclude CI types based on operational responsibility.  
- Class Hierarchy Support: Use operators like “is a” to include parent classes and all extended child classes.

#### Key Exam Tip
- Health Inclusion Rules are the first step in filtering CMDB data for the Health Dashboard.

### CMDB Group Health Dashboard
- Provides an aggregated health view of CIs within a CI group.  
- Shows Correctness, Completeness, and Compliance with drill‑down to issues such as missing fields, audits, duplicates, orphans, and stale CIs.  
- Eliminates the need to switch between individual CI classes.

### Steps to Configure CMDB Health Metrics
1. Configure Staleness, Orphan, Required, Recommended in CI Class Manager.  
2. Task creation is OFF by default (except de‑duplication).  
3. Enable tasks:  
   - CMDB Health Dashboard > Settings → Health Preferences → Health Metrics  
   - Select metric → Create Task = ON  
   - Assign group and save  
4. Run CMDB Health jobs to update dashboard and create tasks.  
5. Job status table: `cmdb_health_metric_status`.

### CMDB Health Remediation
- Applies to Orphan CI, Stale CI, Required & Recommended fields.  
- Enable task creation per metric:  
  - Health Preferences → Health Metrics → Create Task = ON  
- CMDB Remediation Rule links the metric to the workflow.  
- CMDB Health Jobs run → remediation tasks are created.

#### Exceptions (must remember)
- De‑duplication → tasks auto‑created.  
- Compliance audit → configured in CI Class Manager, not via this flow.

### Life Cycle Management (flow)
- **CI & Asset Life Cycle Synchronization**: CIs and Assets share fields (e.g., Serial Number, Model, Assigned to) to keep data consistent.  
- Legacy life cycle fields still widely used:  
  - CI: Install Status, Hardware Status, Operational Status  
  - Asset: State, Substate  
- Do NOT manage all legacy fields → choose one (e.g., Install Status or Hardware Status).

#### CSDM Life Cycle Fields (Recommended)
- Life Cycle Stage  
- Life Cycle Stage Status  
- Introduced to standardize life cycle status and align with CSDM best practices.

#### Synchronization Key Points
- Asset ↔ CI auto‑creation supported in base system.  
- Shared fields sync via Asset–CI Field Mappings table.  
- Legacy life cycle sync is directional (e.g., Asset State → CI Install Status, not always vice versa).

#### Life Cycle Mapping
- Life Cycle Mapping table (`life_cycle_mapping`) maps legacy values → CSDM values.

#### Enable Life Cycle Sync
- One‑time sync of legacy → CSDM fields.  
- Shows Discrepancy Report for unmapped values.  
- After enabling:  
  - Legacy fields ↔ CSDM fields stay synchronized.  
  - Install Base Item (IBI) also stays in sync.

## CMDB Data Manager

One‑line exam takeaway □  
CSDM Life Cycle fields standardize status, legacy fields still exist, and ServiceNow auto‑syncs CI, Asset, and IBI via mapping tables.

### Duplicate CI Remediation Wizard
Identifies and helps resolve duplicate CIs using guided, manual workflows. It supports merge or delete actions but requires user effort for each de‑duplication task.

### De‑Duplication Templates
Enable automated, bulk de‑duplication using configurable matching rules (e.g., class, model, manufacturer). Templates can be scheduled to regularly merge or delete duplicates, but thorough testing is strongly recommended before activation.

### CMDB Insight

### CMDB Query Builder
Enables users to visually build complex queries across CMDB and non‑CMDB tables using a drag‑and‑drop interface. It supports advanced filtering with AND/OR logic but requires a good understanding of the ServiceNow data model and CI relationships.

### Unified Map
Provides an interactive visual map of CIs and their relationships, helping users understand dependencies and assess the impact of changes or incidents. Effective use depends on understanding service‑to‑infrastructure mappings. Accessible from CMDB Workspace. The Unified Map combines: Application Service and Dependency View.

### Intelligent Search
Enhances CMDB search using natural language queries (NLQ) powered by AI. It improves usability by reducing the need for deep technical knowledge while still supporting advanced filtering.

### CMDB and CSDM Data Foundations Dashboards
Offer visibility into CMDB data quality and alignment with CSDM standards, monitor policy compliance, and provide playbooks with best‑practice guidance. Updates may be required via the ServiceNow Store. The remediation playbooks are knowledge articles on the ServiceNow support site that provide context for the respective issue. Each playbook is quite detailed providing a summary of the indicator, an overview of the problem, and why it is important to address the issue.

### CI Class Manager
The CI Class Manager is a centralized tool in ServiceNow for managing CMDB CI classes and their hierarchy. It provides a tree‑view to easily navigate class relationships and understand parent–child dependencies. Through this manager, administrators can create, view, and update CI classes, define attributes, and configure identification and reconciliation rules to improve data accuracy and consistency. It also supports CMDB health and compliance by enabling audits, certification filters, templates, and mandatory/recommended field settings. Additionally, it allows extensibility by creating new child classes or modifying existing ones. The Basic Info tab lets you configure core class details such as the Display Name and control whether the class is extensible, while the Attributes tab focuses on managing class fields and their behavior.

### Principal Class
A Principal Class is a designation assigned to a CI class in the CMDB. When a class is flagged as principal:  
- ITSM processes are streamlined by filtering which CIs appear in the “Configuration Item” reference field in records like incidents, problems, and changes.  
- Only relevant CIs from the designated class are shown, simplifying selection for users.  

Example: Marking the “Servers” class as a Principal Class ensures only server‑related CIs appear in ITSM records, reducing clutter and improving efficiency.

- Managed by group value can be configured through the technical service offering. If it’s set there, it will take precedence over the value set in the CI class Manager.

#### Identification Rules
Identification Rules are used to uniquely identify Configuration Items (CIs) within the CMDB, ensuring each CI is recognized and managed correctly.  
They rely on identifier entries, which define the unique attributes used for identification.  
Common attributes include Name, Serial Number, Device ID, Object ID, Configuration File, Version, and others.  
A CI is considered unique when the defined combination of attributes matches.

**Example:**  
A CI may be uniquely identified using Class + Configuration File + Version.

- **Allow Null Attributes**  
  When enabled, a match is attempted as long as at least one criterion attribute has a value, even if other attributes are null.

- **Allow fallback to parent's rule**  
  Allows the identification rules of the CI’s parent to be used if a match is not found.

#### Dependent Relationships
Dependent relationships describe how one CI relies on another within the IT environment, helping teams understand dependencies and potential impacts.

Key benefits include:
- **Dependency Mapping:** Shows how CIs are connected (e.g., an application depends on a server).  
- **Impact Analysis:** Enables quick assessment of affected services during outages or changes.  
- **Lifecycle Management:** Ensures lifecycle changes (such as decommissioning) are handled correctly for all dependent CIs.

#### Override Dependent Relationship Rule types
Here’s a simple explanation:

- **Hosting**  
  Used for direct hosting relationships.  
  Only one level deep.  
  Typically involves physical or virtual resources.  
  **Example:** Server hosts Application

- **Containment**  
  Used for grouped or hierarchical relationships.  
  Relationships are chained together.  
  One CI type acts as the top-level (root) parent.  
  **Example:** Data Center → Rack → Server

In short:  
- **Hosting** = direct, one-to-one hosting  
- **Containment** = hierarchical, parent–child grouping

#### Reconciliation Rules
Reconciliation rules control how CI data is updated in the CMDB by defining which data sources are allowed to update specific CI attributes and in what priority order. They are configured in the CI Class Manager and help maintain data integrity and consistency.

- Authorize specific discovery or data sources to update CI fields.  
- Prevent lower-priority or unauthorized sources from overwriting trusted data.  
- Resolve conflicts when multiple sources attempt to update the same CI attributes by applying source priority.

#### Data Refresh Rules
Data refresh rules define when CI attributes can be refreshed if a higher-priority data source has not updated the CI within a specified timeframe. This ensures data remains current without compromising source authority.

#### Suggested Relationships
Suggested Relationships are predefined recommendations that guide users in creating logical and meaningful relationships between CIs in the CMDB. They help ensure relationships are accurate and make sense operationally.

Examples:
- **Provides Power for :: Receives Power From**  
  → A rack provides power for a server.  
- **Runs on :: Hosts**  
  → A database runs on a server.  

Illogical relationships (e.g., a rack runs on a server or a server runs on a database) are avoided.

#### Health
The Health tab lets you configure KPIs and metrics to monitor CMDB data quality. Health is measured using three KPIs:

#### Health

Health is measured using three KPIs:

- **Completeness** – Required and recommended CI fields are populated.  
- **Compliance** – CIs adhere to defined audits.  
- **Correctness** – CIs meet data integrity rules, identifying duplicates, orphaned, or stale CIs.

Results are aggregated at the CI class level and then at the overall CMDB level. Health Inclusion Rules define which CIs are included in these calculations.

---

## Identification and Reconciliation Engine (IRE)

The Identification and Reconciliation Engine (IRE) is a central component that ingests healthy data into the CMDB. It ensures accurate and consistent data by identifying and reconciling configuration items (CIs) from multiple data sources. The IRE helps maintain the integrity of the CMDB by reducing duplicate CIs and controlling updates to CIs when multiple data sources—such as Discovery, Service Mapping, Service Graph Connectors, and REST integrations—are used to create and update CI records.

### Features

- **Identification** – Uniquely identifies CIs using identification rules to determine whether a CI already exists in the CMDB or needs to be created.  
- **Reconciliation** – Controls how CI data is updated by allowing only authorized data sources to write to specific CI tables and attributes, ensuring accurate and prioritized data.  
- **De‑duplication** – Detects and groups duplicate CIs into de‑duplication tasks, enabling review and cleanup using built‑in tools like wizards and templates.  
- **Reclassification** – Flags cases where a CI should change its class (upgrade, downgrade, or switch) and creates a task for manual review if automatic reclassification is disabled.

The IRE provides centralized APIs used by discovery and integration tools to enforce identification and reconciliation before data is written to the CMDB. This prevents direct CMDB updates, ensuring data consistency by avoiding duplicates and blocking updates from unauthorized sources.

### Common Issues

- **Duplicate CIs** – Multiple CMDB records represent the same CI due to weak or changing identification rules that fail to uniquely identify each CI.  
- **Overloaded CIs** – Different CIs are mistakenly identified as one, resulting in a single CMDB record where multiple CIs should exist.

### Default Rules

- **Hardware Rule** – Default identification rule for all hardware CIs, applying to the Hardware table and its extended classes (e.g., Server), to manage inserts and updates in the CMDB.  
- **Application Rule** – Default identification rule for application CIs, applied at the Application table level and used when no more specific rules exist for extended application classes.

ServiceNow provides hundreds of rules out‑of‑the‑box to assist with the identification process.

### Criterion Attributes

Criterion attributes are the fields that uniquely define a CI during the IRE identification process. The out‑of‑the‑box (OOB) setup differs from one table/class to another.  
- **Allow null attribute** – When set to false, all criterion attributes must have values to attempt matching with an identifier entry.

For an identification rule to be effective, it must meet these two conditions:

1. The criterion attributes must uniquely identify the CI (e.g., serial number, host name, or install directory).  
2. The rule must be applied to the appropriate table/class and have sufficient specificity to avoid false positives.

### Criterion Attributes

The criterion attributes must remain unchanged throughout the CI’s lifecycle; attributes that can change over time (such as IP address) should not be used.  

If additional rules need to be created beyond the default application identification rules, it is recommended to create good rules that are set with the highest priority for the strongest identifier entries that do not change over time.  

Software applications often lack a unique serial number, so they are best identified by how they run and where they are installed. Because multiple instances of the same application can run on a single host with the same name, using the installation directory or configuration file path or running process command is a best practice. These attributes remain unique for each instance, even on the same machine, making them effective and reliable identifiers.  

**Path not name**  
**System property set to true**

An Advanced Options section on non‑lookup identifier entries becomes available. The Advanced Options section allows the CMDB administrator the ability to set optional conditions to narrow the set of records that will be searched for a matching CI.

#### IRE Support for Non‑CMDB Tables
IRE supports a limited set of base non‑CMDB tables to improve data quality by enforcing identification rules. Supported tables include **Location**, **Department**, **Cost Center**, **Building**, **User**, and **Group**. CI Class Manager is not used; identification rules are created directly on the tables via list views, with one rule allowed per table.

#### Reconciliation Rule: How to Prevent Inserts?
Reconciliation rules help prevent updates from unauthorized or unwanted sources or lower‑priority sources from overwriting data provided by higher‑priority sources, focusing specifically on updates. To further refine control and block inserts from a specific data source, a CMDB administrator can configure IRE Data Source Rules by navigating to:  
`Configuration > Identification/Reconciliation > IRE Data Source Rules`.

When multiple data sources can update the same CI class or attributes, reconciliation rule prioritization determines which source is authoritative. This prevents authorized sources from overwriting each other’s data and ensures a clear source of truth.

The **Data Source Histories** (`cmdb_datasource_last_update`) table in ServiceNow is used to track the last update time for each data source that contributes data to the Configuration Management Database (CMDB). This table is populated only after reconciliation rules are configured for a specific class and data is ingested into that class.

#### CMDB 360 / Multisource CMDB
Before the Paris release, ServiceNow CMDB could track only the last data source that updated a CI or its attributes, stored in the Data Source Histories (`cmdb_datasource_last_update`) table. When multiple discovery sources reported values for the same attribute, lower‑priority values were discarded by reconciliation rules, making it difficult to analyze data conflicts, compare sources, identify gaps, or improve reconciliation logic.

After the Paris release, Multisource CMDB, available through CMDB 360 in CMDB Workspace, was introduced. It retains full attribute‑level history from all discovery sources—both accepted and rejected values—stored in the CMDB MultiSource Data (`cmdb_multisource_data`) table. This enables CMDB administrators to track how each CI is populated, compare values across sources, revert updates from specific sources, recompute attributes after reconciliation rule changes, and better assess data quality and source coverage using CMDB 360 analytics and queries.

#### CMDB 360 / Multisource CMDB

##### Solving the following challenges
- Inability to store all CI data ingested by various discovery sources  
- Inability to find the reported value from multiple discovery sources  
- Inability to remove and replace data from an incorrect discovery source  
- Inability to modify reconciliation rules and recompute the data immediately  

##### Multisource data access
Multisource data can be accessed from a CI record under the **Related Links** or **CI Class Manager** from the **Reconciliation Rule** tab.

##### Data population schedule
The data under the CMDB 360 view populates each day after the following scheduled job executes:
- **Multisource Dashboard Analytics Population**

##### How to enable Multisource CMDB
1. Activate the ITOM Discovery License (`com.snc.itom.discovery.license`) plugin.  
2. Navigate to **All > Configuration > CMDB 360 Properties**.  
3. In the CMDB 360 Properties pane, ensure that the `glide.identification_engine.multisource_enabled` (Enables CMDB 360) property is set to **true**.

##### CI Class Manager (Recompute)
Use the **recompute** option to recalculate CI attribute values when reconciliation rules are modified or a discovery source is found to be invalid. This ensures the updated rules or sources are correctly applied.

##### CMDB 360 Query
CMDB 360 Query is a powerful feature that helps customers explore and analyze CMDB data to answer critical operational questions. It provides three main query options:
- **Explore 360 Data**: Understand what CI data is being reported and by which discovery sources, enabling deep visibility into attribute‑level data.  
- **Identify Data Mismatches**: Detect inconsistencies when multiple data sources report different values for the same CI attribute.  
- **Gap Analysis**: Identify missing or inconsistent discovery coverage, such as when one source reports a CI and another does not.  

Using CMDB 360 Query, administrators can easily find issues like servers missing the ServiceNow Agent Client Collector or Windows servers not discovered by ServiceNow Discovery. Overall, this feature improves CMDB transparency, data quality, and confidence in discovery sources.

##### Dynamic Reconciliation Rules
The **Dynamic Reconciliation Rule** option is only available after the Multisource CMDB is enabled.  
When both static and dynamic reconciliation rules apply to the same CI attribute, the dynamic reconciliation rule takes precedence.  
Dynamic reconciliation rules support several rule types such as:
- First Reported  
- Most Reported  
- Last Reported  
- Largest Value  
- Smallest Value  

The largest and smallest value types only apply to numeric field types. When on the **Select Attributes** tab of the Create Reconciliation Rule wizard, only numeric field types are displayed, and the other attributes are hidden.

##### Key Points to Remember
- Dynamic rules defined within a specific class take precedence over rules defined from a parent class.  
- If no rules are defined for a specific class, rules defined at a parent class apply.  
- If the same CI attribute has both a static reconciliation rule and a dynamic reconciliation rule, the dynamic reconciliation rule takes precedence.  
- The Server class uses a dynamic reconciliation rule that selects the largest value for the RAM field, while the Windows Server class uses a rule that selects the most reported value.  

**Question:**  
Based on the RAM values available from different discovery sources in the Multisource CMDB for a given Windows Server, which RAfv value will ultimately be written to the CMDB for that Windows Server record?

## Identification and Reconciliation Engine (IRE)

### RAM Value Example

**Question:**  
Based on the RAM values available from different discovery sources in the Multisource CMDB for a given Windows Server, which RAM value will ultimately be written to the CMDB for that Windows Server record?

**Discovery Source Values**

| Source          | RAM (MB) |
|-----------------|----------|
| Tivoli          | 40961    |
| ServiceNow      | 4096     |
| LANDesk         | 2048     |
| Altiris         | 6020     |

**Answer:**  
`4096` is the correct value, because the Windows Server class is configured with a dynamic reconciliation rule that selects the **most reported** value. Since ServiceNow reports 4096 twice (once for the Windows Server class and once for the Server class), it is the most frequently reported value and therefore wins the reconciliation.

**Additional Note**  
The Server class uses a dynamic reconciliation rule that selects the **largest** value for the RAM field. However, because the Windows Server class overrides this with a rule that selects the most reported value, the Server class rule does not apply to Windows Server records.

---

## Common Service Data Model (CSDM) Domains and Features

### 1. Business Services, Technology Management Services, Business Service Offerings, and Technology Management Offerings

These can be created using:
- Forms and lists
- **Application Service Wizard** (streamlined method)

### 2. Consequences of Not Aligning with CSDM

Choose **two** of the following potential consequences:
- Potential loss of data  
- Incompatibility with future ServiceNow products  
- Increased technical debt  
- Inability to install ServiceNow Store applications  

### 3. CSDM Domain for Business Applications, Information Objects, and Capabilities

- Design & Planning  
- Build & Integration  
- Service Delivery  
- **Service Consumption**  

### 4. CSDM Domain for Deployed Service Instances and Their Discoverable Components

- **Service Consumption**  
- Design & Planning  
- Service Delivery  
- Build & Integration  
- Ideation & Strategy  

### 5. Three Pillars for a Successful Data Foundation

Choose **three** of the following:
- Compliance  
- **Integrity**  
- Completeness  
- Governance  
- Correctness  
- Insight  

### 6. Feature to Relate Application Service/Service Instance with Technology Management Offering, Business Service Offering, and/or Business Application

- A. Service Builder  
- B. IntegrationHub ETL  
- C. CMDB Workspace  
- D. Application Service Wizard  
- E. **Class Manager**  

### 7. CSDM Domain for Customer Service Management

- Service Delivery  
- Ideation & Strategy  
- Build & Integration  
- Design & Planning  
- **Service Consumption**  

### 8. Unleashed Workspace for Portfolio, Service, Offering, and Product Management

- CMDB Workspace  
- Service Builder  
- Service Operations Workspace  
- **Digital Portfolio Management**  
- Class Manager  

### 9. Lifecycle Management of a Configuration Item (CI)

Recommended CSDM fields to manage CI lifecycle:
- Hardware status  
- Install Status  
- **Lifecycle stage and stage status**  
- Operational status  

### 10. Service Instance Types

Which type represents a logical representation or a deployed application stack and its dependencies?
- Business Application (`cmdb_ci_business_app`)  
- Application Service (`cmdb_ci_service_auto`)  
- Application (`cmdb_ci_application`)  
- **Technology Management Service (`cmdb_ci_service_technical`)**  

### 11. Built‑In Visualization and Reporting Tool for CSDM

Which ServiceNow feature helps assess and improve CSDM implementation based on ServiceNow best practices?
- Class Manager  
- CMDB Health Dashboard  
- **CSDM Data Foundations Dashboard**  
- Application Service Wizard  
- Service Builder  

### 12. Operational Configuration Items for Incident or Change Request Records

Which of the following operational CIs can be selected and populated in the Configuration Item field on an Incident or Change Request record? (Answer list omitted – refer to the full CSDM documentation for details.)

### 12. Operational Configuration Items for Incident or Change Request Records

**Choose 2 answers**

- Installed sortware  
- Business Application  
- Dynamic Cl Group  
- Application service  

---

**From which of the following can the Managed by group be configured and synchronized to the underlying group or class of Configuration Items (Cls)?**  
*Choose 2 answers*

- Technology Management Orterings  
- Technology Management Services  
- Class Manager  
- Business Service Offerings  
- Business services  

---

**Which CSDM domain is an enterprise architect involved in?**

- Idealfon & Strategy  
- Service Consumption  
- Service Delivery  
- Build & Integration  
- Design & Planning  

---

**Aligning to the Common Service Data Model (CSDM) allows for auto‑population of the assignment group held on new Incident and change request records. Which of the following are true when creating a new Incident or Change Request in ServiceNow?**  
*Choose 2 answers*

- A. Change group on the selected Cl auto‑populates the assignment group field on the change request form.  
- B. Managed by group on the selected Cl auto‑populates the assignment group field on the Incident form.  
- C. Support group on the selected Cl auto‑populates the assignment group field on the Incident form.  
- D. Approval group on the selected Cl auto‑populates the assignment group field on the change request form.  

---

#### Quick Study Guide

| Domain | Mental Anchor | Key Keywords |
|--------|---------------|--------------|
| Ideation & Strategy | The 0Goal0Business Capability, Business Unit | — |
| Design & Planning | The 0Blueprint | Business Application, Information Object |
| Build & Integration | The °CreationM | SDLC, DevOps, Microservices |
| Service Delivery | The 00perationM | Application Service, Discovery, Infrastructure |
| Service Consumption | The "ExchangeM | Catalog, CSM, Portfolio, Request |

