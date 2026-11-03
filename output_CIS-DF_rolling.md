# CMDB and CSDM Overview

## CMDB
- The database used to store configuration records throughout their lifecycle.  
- The Configuration Management System maintains one or more CMDBs, each storing attributes of CIs and relationships with other CIs.

## Common Service Data Model (CSDM)
- The data model that determines where to record items in the CMDB and what relationships drive business value.  
- Provides a standard set of service‑related definitions across ServiceNow products and the Now Platform, enabling true service‑level reporting and prescriptive guidance on service modeling.

## Configuration Item (CI)
- Physical and logical components of an infrastructure that need to be managed to deliver a product or service and are currently, or soon will be, under configuration management.  
- Examples: network device, server, application, delivery truck, service.

## Attribute
- Information that further describes a CI, such as name, serial number, manufacturer, operating system.

## Relationship Type
- Defines relationships between configuration items.  
- Example: a web application reads data from a specific database, which in turn depends on a piece of underlying hardware.

## Class
- Describes a table that contains and represents a specific type or group of CIs that share common attributes (e.g., Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, Animal).

## Base Table
- The core Configuration Item `[cmdb_ci]` table, which stores the basic attributes of all CIs.  
- All configuration item classes extend from this table, including all hardware and applications.

## CI Reclassification
- A CI whose class has been upgraded, downgraded, or switched.  
- Example: a Server record upgraded from the Server `[cmdb_ci_server]` class to the Windows Server `[cmdb_ci_win_server]` class.

## Parent and Child Class
- A table that extends another table is called a child class; the table it extends is the parent class.  
- A table can be both a parent and a child, extending and providing extensions for other tables.  
- Example: the Server table extends the Computer table, and the Windows Server table extends the Server table, making the Server table both a parent and child class.

## Asset vs. CI
- **Asset**  
  - Often starts during the procurement process, but may be created when a discovery tool finds the CI for the first time.  
  - Part of the financial lifecycle.  
- **Configuration Item (CI)**  
  - Often starts when a discovery tool finds the CI for the first time, but may be created during the procurement process.  
  - Part of the technical operations.  
- On the Now platform, creating a hardware asset automatically creates a corresponding CI, and vice versa; they are connected throughout the CI/Asset lifecycle.

## Application Service

A set of interconnected applications and hosts which are configured to offer a service to the organization. Application services can be internal, like an organization email system, or customer‑facing, like an organization website.

### Application

Applications that comprise an application service as configuration items (CIs).  
The various applications and the relationships between them that comprise an application service are stored in the CMDB (e.g., Tomcat, Apache, Microsoft SQL, Oracle, IIS).

### DevOps

Consists of developers who build applications and the operations groups who deploy and maintain them within an enterprise.  
In a DevOps environment, these two groups are combined into one to work more effectively together, accelerating and improving service delivery.

### Principal Class

Principle classes can be configured to limit the CI classes that display in the Configuration Item fields on incident, problem, and change records.

### Logical CI

Logical CIs do not take up physical space. They perform specific functions that require physical components to operate.  
Examples include Service Offering, Service, and Business Application, which are manually entered into the CMDB.

#### Examples

1️⃣ **Business Application**  
   *Logical CI:* “Microsoft Teams” (the collaboration/chat app used by employees)  
   *Physical CIs it depends on:*  
   - Cloud servers hosting Teams  
   - Network infrastructure (routers, switches)  
   - Databases storing user info and messages  

2️⃣ **Service**  
   *Logical CI:* “Corporate Email Service”  
   *Physical CIs it depends on:*  
   - Exchange Server or Office 365 backend  
   - Mail servers  
   - Storage for email data  
   - Network connections for email delivery  

3️⃣ **Service Offering**  
   *Logical CI:* “VPN Access for Remote Employees”  
   *Physical CIs it depends on:*  
   - VPN servers  
   - Firewalls  
   - Network links to the corporate office  

4️⃣ **Other Examples**  
   *Logical CI:* “HR Payroll System” – depends on payroll application servers, database servers, authentication servers.  
   *Logical CI:* “Customer‑Facing Website” – depends on web servers, application servers, load balancers, content delivery network.

> 💡 **Tip:** A simple way to think of it:  
> **Logical CI** = What the business sees / uses  
> **Physical CI** = What actually runs it behind the scenes

### Foundation Data

Not part of the CMDB, but referenced in the CI records.  
One of the most important and challenging aspects of CMDB design is selecting the appropriate CI classes, levels, attributes, and relationships to be used as part of a CMDB implementation. During a CMDB health check, ServiceNow examines the number of custom classes and attributes created and assesses whether these custom attributes are established at the correct level. ServiceNow provides a free store application called **CMDB CI Class Models** that can be installed on a ServiceNow instance to obtain a wide range of additional classes that are not provided in a base instance.

### Automated Discovery Tools

- ServiceNow Discovery  
- Service Mapping  
- Agent Client Collector  

### Configuration and Asset Management Lifecycles

An asset becomes a CI (Configuration Item) when it is deployed and remains a CI throughout its lifecycle until it is returned to stock or disposed of. As illustrated in the diagram, Configuration Management and IT Asset Management are distinct, yet complementary practices.

### Change Control Board (CCB)

Form a Configuration Control Board (CCB). The CCB is a team of people that ensures your CMDB delivers continuous value. This team sets direction and makes decisions on what is needed to ensure your CMDB can support your organization’s strategic initiatives and determine if the CMDB is ready for utilization.

## CMDB Data Population & Discovery Methods

### Three Pillars of CMDB Success
- **Ingestion of CMDB data** – How the CMDB is populated and the data is identified and reconciled. Automate as much as possible the flow of data into the CMDB at a frequency that supports your stated use cases.  
- **Governance of the data** – Getting the data in is just the beginning of your CMDB journey. Next is the management and upkeep of the data to maintain a healthy CMDB and gain value from the data.  
- **Insight into the data** – How do you visualize and utilize this data across the platform?

### ServiceNow CMDB Data Population & Discovery Methods (Ingestion)

ServiceNow provides multiple approaches to populate and maintain the CMDB, ranging from automated discovery to integrations and data imports. Each method serves a specific purpose and has licensing and configuration considerations.

#### ServiceNow Discovery (Horizontal / Agentless, IP‑based discovery)
- Automatically discovers infrastructure (servers, network devices, applications).  
- Populates the CMDB and maps dependencies between components.  
- **License**: Paid (ITOM Visibility).  
- **Note**: Discovered data should be enriched with non‑discoverable attributes (e.g., support group, managed by).  
- **Schedule**: Based; not real‑time.  
- Uses probes and sensors to determine the device type.

#### MID Server
- The MID Server (Management, Instrumentation, and Discovery Server) is deployed inside the organization’s trusted network.  
- Acts as a secure bridge between the ServiceNow instance and internal systems that are not directly accessible due to firewalls or network restrictions.  
- All communication between ServiceNow and the MID Server is encrypted.  
- ServiceNow sends probes to the MID Server; the MID Server executes them and returns results, which sensors use to update the CMDB.  
- Discovery is agentless and uses standard protocols:  
  - WMI for Windows  
  - SSH for Linux/Unix  
  - SNMP for network devices  
- The MID Server ensures secure, scalable Discovery without exposing internal systems to the internet.  
- **Key takeaway**: ServiceNow never directly connects to internal devices—everything goes through the MID Server.

#### Discovery Schedules
- Define when, what, and where Discovery runs.  
- Used for horizontal Discovery (network‑based scanning).  
- Specify:  
  - IP ranges / scope  
  - Schedule timing  
  - Assigned MID Server(s)  
- Can target on‑prem environments or cloud service accounts.  
- Schedules trigger Discovery using probes, sensors, and patterns to identify and update CIs in the CMDB.

#### Discovery Admin Workspace (Schedules Page)
- Central hub to monitor and manage Discovery operations.  
- Provides real‑time visibility into Discovery activity and performance.  
- Key reports include:  
  - Schedules by location (map)  
  - Total schedules (last 24 hours)  
  - Errors by category  
  - Total Discovery attempts (completed vs canceled)  
- **Key takeaway**: Discovery Schedules control horizontal Discovery execution and are monitored through the Discovery Admin Workspace.

#### Types of Discovery
- **Network Discovery** – Identifies internal IP address ranges. Not required if IP ranges are already known.  
- **CI Discovery** – Discovers devices, servers, and applications. Most commonly used Discovery type.  
- **Cloud Discovery** – Discovers AWS and Azure resources. Uses cloud credentials and APIs.  
- **Serverless Discovery** – Discovers applications without discovering the host first.

#### Serverless Discovery
Pattern-based and does not rely on traditional host discovery.

> ✔ **Key takeaway:** All are forms of horizontal Discovery, each targeting different environments and use cases.

#### Limiting Discovery Data
- Improves data accuracy  
- Avoids populating the CMDB with low-priority or irrelevant data  
- Establishes a strong foundation with high‑quality CIs  
- Prevents CMDB data overload  
- Reduces clutter caused by unnecessary Discovery results  
- Keeps the CMDB clean and maintainable  
- Faster initial deployment (fewer devices scanned → quicker Discovery cycles)  
- Enables a usable CMDB early, with gradual expansion later  
- Simplifies CMDB management (focuses on key CI classes such as servers and critical applications)  
- Ensures data is immediately relevant to business needs  
- Better stakeholder buy‑in (quick wins with accurate data build trust)  
- Encourages support for broader Discovery adoption later  

> ✔ **Key takeaway:** Start small, discover what matters first, then expand Discovery incrementally.

#### Discovery Ranges
Discovery ranges define which IP addresses ServiceNow Discovery scans. You can include or exclude specific IP ranges in a Discovery schedule.

##### Broad Ranges (Subnets)
- Example:  
  - `192.168.0.0/24`  
  - `10.11.128.192/26`  
- Includes network and broadcast addresses.  
- Scans a large number of IPs, which may cause:  
  - Data overload  
  - Redundant or irrelevant CIs  
  - Discovery errors  
- Not recommended during initial implementation.  
- **Best practice:** Do not exceed `/16` (~65,000 IPs); split into smaller ranges if needed.

##### Limited Ranges (Preferred Initially)
- Example:  
  - `192.168.0.1 – 192.168.0.254`  
  - `10.11.128.193 – 10.11.128.254`  
- Excludes network and broadcast addresses.  
- Targets specific, known devices.  
- Improves data quality, performance, and troubleshooting.  
- Supports clean and manageable CMDB growth.

> ✔ **Key takeaway:** Start with small, targeted IP ranges and expand Discovery gradually to avoid CMDB data overload.

#### Discovery Configuration Console
Used to control what Discovery detects (devices, applications, software, and CIs).  
Allows including or excluding specific CI types from Discovery.  
Excluding a CI disables the related probe or classifier.  
Helps CMDB teams focus on principal CI classes only.  
Reduces noise, unnecessary data, and CMDB clutter.  

**Access path:** `Discovery Definition → Configuration Console`

> ✔ **Key takeaway:** Use the Configuration Console to limit Discovery to only the CIs you want to manage.

#### Discoverable Data
Discoverable data is the hardware, software, and network information collected by ServiceNow Discovery.

Common examples include:
- **Hardware:** CPU, memory, storage  
- **Software:** operating systems, installed applications  
- **Network:** IP address, MAC address, topology  
- **Cloud resources:** AWS, Azure, Google Cloud  

Discovery runs on a scheduled basis to keep the CMDB up to date with infrastructure changes.

##### Discovery Source Field
- Newly discovered CIs are created with `Discovery source = ServiceNow`.  
- If a CI already exists (e.g., created via Asset Management), the source may initially be `SNAssetManagement`.  
- Once discovered, the Discovery source is updated to ServiceNow.  

> ✔ The Discovery source always reflects the last authoritative discovery method.

#### Non-Discoverable Data
Non‑discoverable data cannot be collected by automated tools like Discovery, Service Mapping, or Service Graph Connectors.  
Must be manually maintained or populated via automation after Discovery.  
Used to support ITSM processes such as Incident, Change, and Problem Management.

Common Non‑Discoverable Fields:
- Assigned to  
- Owned by  
- Support group  
- Change group  
- Managed by group  
- Location  

Accurate group data is critical for:
- Proper incident routing  
- Efficient change execution

##### Operational accountability
- ✔ **Key takeaway:** Discovery populates technical CI data; CMDB admins must enrich CIs with non‑discoverable ownership and group information.

##### Service Mapping (Top‑Down / ML‑Powered, Tag‑based discovery)
- Builds end‑to‑end service maps showing how business services are supported by IT components.
- Dynamically updates relationships as changes occur.
- **License:** Paid (ITOM Visibility).
- **Note:** Follow CSDM guidelines, define service owners, and relate services to business applications.

##### Business Value
- Bridges the gap between IT Operations and business users.
- Aligns IT service delivery with business outcomes, not just infrastructure.
- Supports ITSM processes: Incident, Problem, and Change Management.

##### Key Concepts
- **Application Service:** Logical representation of a deployed system, application, or product stack.  
  Operational CI used in ITSM/ITOM practices.  
  Can be environment‑specific (Dev, Test, QA, Prod) or region‑specific (AMS, EMEA, APJ).  
  Stored in `cmdb_ci_service_auto` or sub‑classes.
- **Service Map:** Shows which CIs support a service, including applications, servers, middleware, and networks.  
  Helps identify service impact when components fail.

##### Types of Application Services
###### Top‑Down Mapping
- **Pattern‑Based:**  
  - Best for: Mission‑critical apps.  
  - Level: Surgical / Process‑to‑process.  
  - Key: Most granular.
- **ML Connection Suggestions:**  
  - Best for: Homegrown & custom COTS.  
  - Level: Traffic‑based / Fingerprinting.  
  - Key: Fastest time‑to‑value.  
  - *Note:* These two can be used together or individually.

###### Tag‑Based Mapping
- Best for: Cloud‑native, containers, and VMs.  
- Effort: Medium touch (requires defining tag categories/families).  
- Key: Visualizes resource stacks across cloud infrastructure.

###### Dynamic CI Group
- Best for: Small application services.  
- Mechanism: Uses CI list filters or CMDB queries.  
- Effort: High touch (requires manual query building).  
- Key: No license required.

##### Integration with CSDM
- Supports Common Service Data Model (CSDM) by automating service and dependency modeling.
- Benefits include:
  - Accurate service modeling
  - Enhanced CMDB data quality
  - Dependency management for impact analysis and operational support

##### Benefits
- Enhanced visibility of IT services and dependencies
- Faster root‑cause analysis for incidents and problems
- Proactive, low‑risk change management
- Improved compliance and governance through clear documentation

- ✔ **Key takeaway:** Service Mapping automates discovery and mapping of services and their dependencies, enabling IT teams to make informed decisions, reduce downtime, and improve service quality aligned with business objectives.

##### Agent Client Collector (ACC – Agent‑Based)
- Requires installing an agent on each host.
- Provides real‑time endpoint visibility.
- Collects hardware, software inventory, configuration details, and software usage data (key for SAM).
- **Configuration Details:** Captures system configuration details, including OS settings, patch levels, and network configurations.
- **License:** Paid.
- **Note:** Agent deployment is mandatory.
- Choose ACC when the scenario mentions:
  - Laptops / workstations that are not always connected to the corporate network
  - Remote users, VPN‑based access, or devices that connect intermittently
  - Security restrictions where the security team does not allow inbound scans or remote connections
  - Highly secured / isolated networks (DMZ, restricted zones)
  - Requirement to collect OS, software, processes, or security data directly from the endpoint
  - Need for a single lightweight agent instead of multiple tools

##### IntegrationHub ETL
- Automates extract, transform, and load processes into CMDB and other tables.
- Supports data normalization and scheduled automation.
- **License:** No (available via ServiceNow Store).
- **Note:** Requires good understanding of ServiceNow and source data models.

##### Non‑CMDB Table Support for IntegrationHub ETL
- IH‑ETL includes advanced functionality that allows data ingestion into non‑CMDB tables.

##### Non‑CMDB Table Support for IntegrationHub ETL
- **Location** – `cmn_location`
- **Department** – `cmn_department`
- **Cost Center** – `cmn_cost_center`
- **Building** – `cmn_building`
- **User** – `sys_user`
- **Group** – `sys_user_group`

#### Discovery and Service Mapping Patterns Application
- The Discovery and Service Mapping Patterns application is a ServiceNow Store app.
- New discovery patterns are released regularly through the ServiceNow Store, independent of major platform releases.  
  This enables Discovery and Service Mapping customers to receive new or updated patterns without waiting for a full ServiceNow upgrade.

#### Service Graph Connectors
- Pre‑built integrations to sync data from external systems (e.g., Azure, Intune, MS SCCM, Jamf, AWS).  
- Ensures CMDB data consistency across tools.  
- Can automatically synchronize and update the CMDB in real‑time or on a scheduled basis, reducing manual data entry and improving efficiency.  
- **License:** Paid (except SCCM connector, which is free).  
- **Note:** Requires credentials for target systems.

#### Import Sets & Transform Maps (Legacy Method)
- Imports data from files, databases, or APIs into staging tables.  
- Supports field mapping and transform scripts.  
- **License:** No.  
- **Note:** Does not use IRE by default, risking duplicates—recommended to enforce IRE via transform scripts.

#### Utilizing IRE during a CMDB Import
- The Identification and Reconciliation Engine (IRE) centrally identifies and reconciles CI data from multiple sources, including manual imports.  
- Identification rules are defined per CI class and consist of identifier entries (unique attribute sets with priorities) and related entries.  
- By default, IRE is not used during imports. It must be explicitly enabled using a custom `onBefore` script in the transform map.  
- The `CMDBTransformUtil` API sends import set data to the IRE for identification before insert/update.  
- IRE determines whether a CI is new or existing:  
  - **New CI** → Insert into CMDB  
  - **Existing CI** → Update the existing record  
- When using `CMDBTransformUtil`, coalesce settings are ignored and are not required.

#### Data Manager
- Data Manager enables periodic certification and auditing of CMDB data to ensure accuracy and completeness.  
- It uses scheduled certification policies that assign verification tasks to responsible users or groups.

#### CI Attribute Population Using Technology Management Offering
1. **Create a CMDB Group**  
2. **Create a Dynamic CI Group**  
3. **Create a Technology Management Service**  
4. **Create a Technology Management Offering**  
5. **Associate Dynamic CI Group to the Offering**  

- **Automatic Group Synchronization**  
  - System Business Rule (CSDM – Sync Group Attributes) syncs group values.  
  - Service Builder is an alternative UI to achieve the same result, but it needs to be installed first from the ServiceNow Store application.

## Management Tools Overview

### CMDB Workspace

### CMDB Governance

### CMDB Health Dashboard

Monitors overall CMDB data quality through scorecards for Completeness, Correctness, and Compliance. It highlights top CI classes impacting health and allows drill‑down analysis. Scheduled jobs must be manually activated for scorecards to populate.

#### Purpose
Provides a quick view of the overall quality of CMDB data using three key scorecards.

#### Completeness
Measures whether CIs have all required and recommended fields populated, including non‑discoverable data (e.g., ownership, support group).

- **Exam Tip:** Missing essential data lowers completeness. Uses Recommended and Required metrics.
- ServiceNow does not provide predefined required or recommended CI attributes in the CMDB. These must be defined by the CMDB administrator and relevant stakeholders based on process requirements.
- To prevent integrations (including Discovery and IRE) from failing due to missing mandatory CMDB attributes, ServiceNow provides two ways to override the default behavior:
  - **Via CMDB Properties UI**  
    Navigate to **Configuration > CMDB Properties > Identification/Reconciliation Properties**.  
    Find “Enforce the requirement that required attributes cannot be null during identification and reconciliation”, deselect the checkbox (set to false) and save.
  - **Via System Properties (sys_properties.list)**  
    Locate the property `glide.required.attribute.enabled` and set its value to false.
- 👉 **Exam takeaway:** Both methods disable enforcement of required attributes during IRE identification and reconciliation, allowing integrations to proceed even when mandatory fields are missing.

#### Compliance
Shows how well CIs adhere to defined standards and audit policies. Uses the Audit metric.

- **Exam Tip:** Evaluates alignment with desired state configurations.
- Compliance audits verify that CIs meet defined standards or policies. Typical examples include ensuring antivirus is installed, systems are patched to required levels, and mandatory ownership fields (such as Support Group and Managed by Group) are populated.
- A common use case is system upgrades, where compliance audits identify servers that do not meet minimum hardware requirements (disk space, RAM, CPU) needed for the next upgrade. The Compliance Scorecard highlights non‑compliant CIs so issues can be addressed before the upgrade.

#### What Compliance Is Based On
Audits comparing actual CI values vs expected values.

- Expected values are defined via:
  - Certification Templates
  - Scripted Audits

#### Common Audit Examples
- Antivirus installed on all workstations
- Linux servers on latest patch
- Production servers have Support Group and Managed by Group
- Hardware readiness for OS upgrades (RAM, disk, CPU)

#### Key Rule (Very Important for Exam ❗)
- ✅ **Only these audit types appear in the CMDB Health Dashboard Compliance Scorecard:**
  - Desired State audits
  - Scripted audits
- 🚫 **NOT included in the scorecard:**
  - Compliance
  - Compliance Architecture

#### Compliance Scorecard Configuration (4 Required Components)

1️⃣ **Certification Filter**  
Defines scope of the audit (which CIs).  
Based on CI class and conditions.  
Examples:  
- All Windows Computers  
- All UNIX servers in a datacenter  
Navigation: **CI Class Manager → Health → Compliance** or **Compliance → Filters**

2️⃣ **Certification Template**  
Defines conditions to pass the audit.  
Can check:  
- Attributes  
- Relationships  
- Reference fields  
Must reference a Certification Filter.  
Audit type must be = Desired State.  
Navigation: **CI Class Manager → Health → Compliance** or **Compliance → Templates**

3️⃣ **Audit**  
Executes the comparison:

#### Compliance Scorecard Configuration (4 Required Components)

3️⃣ **Audit**  
- **Filtered CIs vs Template conditions**  
- Can be scheduled  
- Create remediation tasks and assign to a user or a group to work on it  
- Uses the standard ServiceNow scheduler  
- Navigation:  
  - CI Class Manager → Health → Compliance  
  - OR Compliance > Audits  

##### Scripted Audits  
- Used when templates are too restrictive  
- Logic is defined in a script  
- Still use a Certification Filter  
- Included in the Compliance Scorecard  
- Cannot be created via CI Class Manager  
- Navigation: Compliance > Desired State > Scripted Audits > Audits  
- Base system includes samples:  
  - Data Center Zone Usage  
  - Desired State vs Data Manager (Exam Favorite 💡)  
- CMDB Health Desired State Audits are automatic and ensure fields are present and configured correctly (e.g., a server has an owner and support group)  
- Data Manager Certification Policies are used for manual verification when data cannot be discovered automatically, generating certification tasks/checklists (e.g., confirm Joe Smith is the correct owner of ServerXYZ)  
- 👉 They serve different purposes and are NOT the same  

4️⃣ **Compliance Score Calculation Job**  
- Calculates the Compliance KPI after audits run  
- **Scheduled Job**: CMDB Health Dashboard – Compliance Score Calculation  
- **Navigation**: Configuration > Health Preferences > Scheduled Jobs  
- **Must be**:  
  - Activated  
  - Run by a user with an admin role  
- **Status table**: `cmdb_health_metric_status`  
- ⚠️ If run by a non‑admin → inaccurate results  

#### Correctness  
Checks the accuracy of CMDB data, including duplicates, outdated CIs, and proper relationships. Uses the Duplicate, Orphan, and Staleness metrics.  
- **Exam Tip**: A CI passes correctness only if it meets all defined metrics.  
- **Score Calculation**: Overall percentage = % of CIs that pass all metrics, not an average of individual metrics.  
  - Example: Metrics 93 %, 100 %, 96 % → overall = 89 % (because only 89 % of CIs met all metrics).  

##### Duplicate CIs Definition  
- Occurs when multiple CMDB records exist for a single real‑world CI.  
- **Key Points**  
  - Evaluated using predefined identification rules.  
  - Only independent CIs are evaluated (e.g., hardware, servers – not applications).  
  - Duplicates can be detected via:  
    - ServiceNow Discovery  
    - CMDB Correctness job  
- **Behavior**  
  - A de‑duplication task is automatically created.  
  - The oldest CI record (based on `sys_created_on`) is treated as the primary (non‑duplicate).  
  - Newer records are marked as duplicates via the `Duplicate Of` field.  
- **Insights Provided**  
  - Classes with the highest number of duplicates.  
  - Discovery sources or CI owners causing duplication (root‑cause analysis).  

##### Orphan CIs Definition  
- CIs that lack required relationships with other CIs.  
- **Key Points**  
  - No base system orphan rules exist by default.  
  - Orphan tracking requires custom orphan rules.  
  - Only one orphan rule per class is allowed.  
- **Examples**  
  - Application with no `Runs

##### Staleness Rules
- **Servers discovered daily → staleness = 7 days**  
- **Why It Matters**  
  - Prevents use of non‑existent or outdated CIs  
  - Critical for lifecycle management and downstream processes  
- **Configuration & Governance**  
  - **CI Class Manager**  
    - Used to configure Correctness Scorecard rules  
    - Supports:  
      - Duplicate identification  
      - Orphan rules  
      - Staleness rules by class  

##### Exam Takeaways (High‑Probability Questions)
- ✅ Correctness Scorecard measures Duplicate, Orphan, and Stale CIs  
- ✅ Duplicate metric applies only to independent CIs  
- ✅ Oldest CI = primary, newer ones = duplicates  
- ✅ No default orphan rules → must be configured manually  
- ✅ Base staleness rule = 60 days at `cmdb_ci`  
- ✅ `sys_updated_on` drives staleness calculation  
- ✅ Metrics roll up into the CMDB Health Dashboard  

##### Duplicate CIs Management
- **What Are Duplicate CIs?**  
  - Two or more CMDB records representing the same real‑world item.  
  - Negatively impact:  
    - Incident, Change, and Problem Management  
    - Reporting & compliance  
    - Trust in CMDB data  

- **Common Causes of Duplicate CIs**  
  - Discovery tools (multiple tools discovering the same CI differently)  
  - Import Sets without proper identification rules  
  - Third‑party integrations (REST/SOAP) without IRE logic  
  - Manual CI creation (poor governance, no naming standards)  
  - Incorrect or missing Identification Rules  
  - Lack of CMDB governance  

- **How ServiceNow Determines Duplicates**  
  - Duplicates are detected by the Identification and Reconciliation Engine (IRE).  
  - **IRE uses:**  
    - Identification Rules → determine what uniquely identifies a CI  
    - Reconciliation Rules → determine which data source wins  
  - If multiple CIs match identification rules:  
    - A de‑duplication task is created  
    - Visible in CMDB Workspace  
  - ⚠️ **Important Exam Gotcha**  
    - If duplicate CIs already have a Discovery Source populated, the CMDB Health Dashboard Correctness Scorecard will NOT flag them.  
    - Once rediscovered and reprocessed by IRE, they will be flagged and a de‑duplication task is generated.  
    - Duplicate CIs are only flagged by CMDB Health after they are processed by IRE – existing duplicates with a populated Discovery Source are ignored until rediscovery happens.  

- **Discovery Behavior with Duplicates**  
  - When duplicates are found during Discovery:  
    - Oldest CI (by creation date) is updated  
    - Others are marked as duplicates  

- **Key Field Change (Important Update 🚨)**  
  - **Old:** Discovery Source field was used to indicate duplicates  
  - **New:** `Duplicate of` field  
  - *Reason:* Preserve the Discovery Source with the last discovery tool; functionality remains the same  

- **De‑duplication Tasks**  
  - Created automatically when IRE detects duplicates  
  - Allow admins to:  
    - Review duplicate CIs  
    - Decide how to remediate them  
  - **Access:**  
    - Legacy: De‑duplication Tasks module  
    - Current: CMDB Workspace  

- **Duplicate CI Remediator**  
  - Wizard launched from a de‑duplication task  
  - Admin can:  
    - Select Main CI  
    - Merge attributes  
    - Maintain audit trail  
  - **Supports:**  
    - Merge  
    - Retain one CI  
    - Eliminate duplicates  

- **De‑duplication Templates**  
  - Used for bulk remediation:  
    - Pre‑configured remediation logic  
    - Applied per CI class or in bulk  
  - Managed from: De‑duplication Dashboard in CMDB Workspace  
  - Templates can be organized into libraries and executed on multiple de‑duplication tasks at once  

- **System Properties for Duplicate Handling**  
  - **Behavior:**  
    - If duplicates < threshold:  
      - Oldest CI is updated  
      - Others get `Duplicate of` populated  
    - IRE ignores CIs where `Duplicate of` is populated  

##### Now Assist for CMDB (AI‑based)
- Uses Generative AI to assist with CMDB tasks (configuration, remediation, reporting, etc.) – no configuration required.

#### Automates
- Duplicate CI detection  
- CI summarization  
- Suggested remediation steps  

#### Works with
- De‑duplication templates  
- CMDB Workspace  

#### Goal
- Reduce manual effort  
- Improve CMDB accuracy & governance  

#### Why Handling Duplicates Matters (Exam Framing)  
Ensures CMDB as a Single Source of Truth  

Improves:  
- IT operations  
- Reporting & compliance  
- Decision‑making  

#### One‑Line Exam Summary  
Duplicate CIs are identified by the IRE using identification rules, managed via de‑duplication tasks in CMDB Workspace, remediated using the Duplicate CI Remediator or de‑duplication templates, and flagged using the **Duplicate of** field—not Discovery Source.  

#### CI Reclassification & Restriction Rules — Exam Notes (Concise)  

##### CI Reclassification — Core Concepts  
Reclassification = moving a CI to another class during IRE identification  
Happens when CI data is placed in the wrong CMDB class  

##### Reclassification Types  
- **Upgrade** → more specific (Server → Windows Server)  
- **Downgrade** → less specific (Windows Server → Server)  
- **Switch** → different branch (Linux Server ↔ Windows Server)  

##### Default behavior  
Automatic reclassification is enabled  

##### Reclassification Behavior Questions  
**Which of the following reclassification behaviors might cause CI attributes and their data to be excluded during the reclassification process?

## CMDB Health Dashboard

### ✅ Correct
- IP Router **IS** allowed to be downgraded  
- IP Router CI attributes **CAN** be updated  
- *(Restriction applies only to Server and its child classes)*  

### One‑Line Memory Hook
**CMDB Health** = Completeness (fields), Compliance (standards), Correctness (accuracy); overall % = CIs passing all metrics.

### Health Inclusion Rules
- **Purpose:** Define which CI classes are evaluated by the CMDB Health Dashboard (Correctness, Completeness, Compliance).  
- **Why needed:** Discovery tools can populate large volumes of CIs; not all are owned or managed by the organization.  
- **Best practice:** Include only CI classes your organization is responsible for to ensure meaningful and performant health metrics.  
- **Key capabilities:**  
  - *Selective Class Tracking:* Limit health calculations to relevant CI classes.  
  - *Metric‑Level Control:* Apply rules to specific metrics (e.g., Correctness only).  
  - *Customizable Scope:* Include or exclude CI types based on operational responsibility.  
  - *Class Hierarchy Support:* Use operators like “is a” to include parent classes and all extended child classes.  
- **Exam tip:** Health Inclusion Rules are the first step in filtering CMDB data for the Health Dashboard.

### CMDB Group Health Dashboard
- Provides an aggregated health view of CIs within a CI group.  
- Shows Correctness, Completeness, and Compliance with drill‑down to issues such as:  
  - missing fields  
  - audits  
  - duplicates  
  - orphans  
  - stale CIs.  
- Eliminates the need to switch between individual CI classes.

### Steps to Configure CMDB Health Metrics
1. **Configure** Staleness, Orphan, Required, Recommended in CI Class Manager.  
2. **Task creation** is OFF by default (except de‑duplication).  
3. **Enable tasks:**  
   - CMDB Health Dashboard > Settings → Health Preferences → Health Metrics  
   - Select metric → **Create Task = ON**  
   - Assign group and save.  
4. **Run CMDB Health jobs** to update dashboard and create tasks.  
5. **Job status table:** `cmdb_health_metric_status`.

### CMDB Health Remediation
- Applies to Orphan CI, Stale CI, Required & Recommended fields.  
- **Enable task creation per metric:**  
  - Health Preferences → Health Metrics → Create Task = ON.  
- **CMDB Remediation Rule** links the metric to the workflow.  
- **CMDB Health Jobs run** → remediation tasks are created.

#### Exceptions (must remember)
- **De‑duplication** → tasks auto‑created.  
- **Compliance audit** → configured in CI Class Manager, not via this flow.

### Life Cycle Management (flow)

#### CI & Asset Life Cycle Synchronization
- CIs and Assets share fields (e.g., Serial Number, Model, Assigned to) to keep data consistent.  
- Legacy life cycle fields still widely used:  
  - CI: Install Status, Hardware Status, Operational Status  
  - Asset: State, Substate  
- **Do NOT** manage all legacy fields; choose one (e.g., Install Status or Hardware Status).

#### CSDM Life Cycle Fields (Recommended)
- **Life Cycle Stage**  
- **Life Cycle Stage Status**  
- Introduced to standardize life cycle status and align with CSDM best practices.

#### Synchronization Key Points
- Asset ↔ CI auto‑creation supported in base system.  
- Shared fields sync via Asset–CI Field Mappings table.  
- Legacy life cycle sync is directional (e.g., Asset State → CI Install Status, not always vice versa).

#### Life Cycle Mapping
- `life_cycle_mapping` table maps legacy values → CSDM values.

#### Enable Life Cycle Sync
- One‑time sync of legacy → CSDM fields.  
- Shows Discrepancy Report for unmapped values.  
- After enabling:  
  - Legacy fields ↔ CSDM fields stay synchronized.  
  - Install Base Item (IBI) also stays in sync.

> **One‑line exam takeaway**  
> CSDM Life Cycle fields standardize status, legacy fields still exist, and ServiceNow auto‑syncs CI, Asset, and IBI via mapping tables.

## CMDB Data Manager
- Manages the CMDB data lifecycle and governance.  
- Supports data certification, lifecycle policies (retire, archive, delete), and attestation policies to validate the existence of infrastructure and applications.  
- Some lifecycle actions require active lifecycle rules per CI class.

## Duplicate CI Remediation Wizard
- Identifies and helps resolve duplicate CIs using guided, manual workflows.  
- Supports merge or delete actions but requires user effort for each de‑duplication task.

## De‑Duplication Templates
- Enable automated, bulk de‑duplication using configurable matching rules (e.g., class, model, manufacturer).  
- Templates can be scheduled to regularly merge or delete duplicates; thorough testing is strongly recommended before activation.

## CMDB Insight
- Provides visibility into CMDB data quality and alignment with CSDM standards.  
- Monitors policy compliance and offers playbooks with best‑practice guidance.  
- Updates may be required via the ServiceNow Store.  
- Remediation playbooks are knowledge articles on the ServiceNow support site that provide context for the respective issue, including a summary of the indicator, an overview of the problem, and why it is important to address the issue.

## CMDB Query Builder
- Enables users to visually build complex queries across CMDB and non‑CMDB tables using a drag‑and‑drop interface.  
- Supports advanced filtering with AND/OR logic but requires a good understanding of the ServiceNow data model and CI relationships.

## Unified Map
- Provides an interactive visual map of CIs and their relationships, helping users understand dependencies and assess the impact of changes or incidents.  
- Accessible from CMDB Workspace.  
- Combines Application Service and Dependency View.

## Intelligent Search
- Enhances CMDB search using natural language queries (NLQ) powered by AI.  
- Improves usability by reducing the need for deep technical knowledge while still supporting advanced filtering.

## CMDB and CSDM Data Foundations Dashboards
- Offer visibility into CMDB data quality and alignment with CSDM standards.  
- Monitor policy compliance and provide playbooks with best‑practice guidance.

## CI Class Manager
- Centralized tool for managing CMDB CI classes and their hierarchy.  
- Provides a tree‑view to navigate class relationships and understand parent–child dependencies.  
- Allows creation, viewing, and updating of CI classes, definition of attributes, and configuration of identification and reconciliation rules.  
- Supports CMDB health and compliance by enabling audits, certification filters, templates, and mandatory/recommended field settings.  
- Extensibility: create new child classes or modify existing ones.  
- **Basic Info tab**: configure core class details such as Display Name and extensibility.  
- **Attributes tab**: manage class fields and their behavior.

## Principal Class
- A designation assigned to a CI class in the CMDB.  
- When flagged as principal, ITSM processes are streamlined by filtering which CIs appear in the “Configuration Item” reference field in records like incidents, problems, and changes.  
- Only relevant CIs from the designated class are shown, simplifying selection for users.  
- Example: marking the “Servers” class as a Principal Class ensures only server‑related CIs appear in ITSM records, reducing clutter and improving efficiency.

## CI Class Manager Configuration

- Managed by group value can be configured through the technical service offering. If set there, it will take precedence over the value set in the CI class Manager.

### Identification Rules
- Used to uniquely identify Configuration Items (CIs) within the CMDB, ensuring each CI is recognized and managed correctly.
- Rely on identifier entries, which define the unique attributes used for identification.
- Common attributes include Name, Serial Number, Device ID, Object ID, Configuration File, Version, and others.
- A CI is considered unique when the defined combination of attributes matches.
- **Example**: Class + Configuration File + Version.
- **Allow Null Attributes** – When enabled, a match is attempted as long as at least one criterion attribute has a value, even if other attributes are null.
- **Allow fallback to parent's rule** – Allows the identification rules of the class’s parent to be used if a match is not found.

### Dependent Relationships
- Describe how one CI relies on another within the IT environment, helping teams understand dependencies and potential impacts.
- **Key benefits**:
  - **Dependency Mapping** – Shows how CIs are connected (e.g., an application depends on a server).
  - **Impact Analysis** – Enables quick assessment of affected services during outages or changes.
  - **Lifecycle Management** – Ensures lifecycle changes (such as decommissioning) are handled correctly for all dependent CIs.
- **Override Dependent Relationship Rule types**:
  - **Hosting** – Used for direct hosting relationships. Only one level deep, typically involving physical or virtual resources.  
    *Example*: Server hosts Application.
  - **Containment** – Used for grouped or hierarchical relationships. Relationships are chained together, with one CI type acting as the top-level (root) parent.  
    *Example*: Data Center → Rack → Server.
  - **In short**: Hosting = direct, one-to-one hosting; Containment = hierarchical, parent–child grouping.

### Reconciliation Rules
- Control how CI data is updated in the CMDB by defining which data sources are allowed to update specific CI attributes and in what priority order.
- **Authorise specific discovery or data sources** to update CI fields.
- **Prevent lower-priority or unauthorized sources** from overwriting trusted data.
- **Resolve conflicts** when multiple sources attempt to update the same CI attributes by applying source priority.

### Data Refresh Rules
- Define when CI attributes can be refreshed if a higher-priority data source has not updated the CI within a specified timeframe.
- Ensures data remains current without compromising source authority.

### Suggested Relationships
- Predefined recommendations that guide users in creating logical and meaningful relationships between CIs in the CMDB.
- **Examples**:
  - *Provides Power for :: Receives Power From* – e.g., a rack provides power for a server.
  - *Runs on :: Hosts* – e.g., a database runs on a server.
- **Avoid illogical relationships** (e.g., a rack runs on a server or a server runs on a database).

### Health
- The Health tab lets you configure KPIs and metrics to monitor CMDB data quality.
- Health is measured using three KPIs: *(details to follow)*