The CMDB is the database while the Common Service Data Model (CSDM) is the data model. The data model helps determine where to record items in the CMDB, and what relationships are important to drive business value.

Configuration Item (CI)

Physical and logical components of an infrastructure that needs to be managed to deliver a product or service and are currently, or soon will be, under configuration

management. For example, a network device, a server, an application, a delivery truck, or service.

Attribute

Information that further describes a CI such as a name, serial number, manufacturer, operating system.

Relationship Type

Include the relationships between configuration items. For example, a web application might read data from a specific database, which in turn might depend on a piece of underlying hardware.

Class

Describes a table that contains and represents a specific type or group of CIs that share common attributes such as a Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, Animal etc.

Configuration Management Database (CMDB)

A database used to store configuration records throughout their Lifecycle. The Configuration Management System maintains one or more CMDBs, and each CMDB stores attributes of CIs, and Relationships with other CIs.

Base Table

The core Configuration Item [cmdb_ci] table, which stores the basic attributes of all the CIs. All configuration item classes extend from this table including all hardware and applications.

## CI Reclassification

Is a CI whose class has been upgraded, downgraded, or switched. An example of an upgraded CI is a Server record that was upgraded from the Server [cmdb_ci_server] class to the Windows Server [cmdb_ci_win_server] class.

Parent and Child Class

A table that extends another table is called a child class, and the table it extends is the parent class. A table can be both a parent and child class both extending and providing extensions for other tables. For example, the Server table extends the Computer table and the Windows Server table extends the Server table, thus making the Server table both a Parent and Child class.

Asset vs. CI

On the Now platform, when creating a hardware asset, a corresponding CI will be automatically created or when a CI is discovered for the first time and inserted into the CMDB, a corresponding asset record will be automatically created. The asset and the CI is connected through out the CI/Asset lifecycle.

## Asset:

- Often starts during the procurement process, but may be created when a discovery tool finds the CI for the first time
- Is part of the financial lifecycle
## Configuration Item (CI):

- Often starts when a discovery tool finds the CI for the first time, but may be created during the procurement process
- Is part of the technical operations
Common Services Data Model (CSDM)

Represents a standard and shared set of service related definitions across ServiceNow products and the NOW platform that enables and supports true service level reporting while providing prescriptive guidance on service modeling within the CMDB. These

service-related definitions span the ServiceNow® product portfolio and the Now Platform®.

Application Service

A set of interconnected applications and hosts which are configured to offer a service to the organization. Application services can be internal, like an organization email system

or customer-facing, like an organization website.

Application

Applications that comprise an application service as configuration items (CIs). The various Applications and the relationships between them, that comprise an application service, are stored in the CMDB. (i.e. Tomcat, Apache, Microsoft SQL, Oracle, IIS).

DevOps

Consists of developers who build applications and the operations groups who deploy and maintain them within an enterprise. In a DevOps environment, these two groups are combined into one in order to work more effectively together to accelerate and improve service delivery.

Principal Class

Principle Classes can be configured to limit the CI classes that display in the Configuration Item fields on incident, problem, and change records.

Logical CI

Do not take up space. They perform specific functions requiring physical components in order to operate. Examples include Service Offering, Service, Business Application which are manually entered into the CMDB.

Examples:

### 1️⃣ Business Application

- Logical CI: “Microsoft Teams” (the collaboration/chat app used by employees)
## Physical CIs it depends on:

- Cloud servers hosting Teams
- Network infrastructure (routers, switches)
- Databases storing user info and messages
### 2️⃣ Service

- Logical CI: “Corporate Email Service”
## Physical CIs it depends on:

- Exchange Server or Office 365 backend
- Mail servers
- Storage for email data
- Network connections for email delivery
### 3️⃣ Service Offering

- Logical CI: “VPN Access for Remote Employees”
## Physical CIs it depends on:

- VPN servers
- Firewalls
- Network links to the corporate office
### 4️⃣ Other Examples

- Logical CI: “HR Payroll System”
- Depends on: Payroll application servers, database servers, authentication servers.
- Logical CI: “Customer-Facing Website”
- Depends on: Web servers, application servers, load balancers, content delivery network.
💡 Tip: A simple way to think of it:

Logical CI = What the business sees / uses

Physical CI = What actually runs it behind the scenes

Foundation data:

Not part of the CMDB, but referenced In the CI records.

One of the most important and challenging aspects of CMDB design is selecting the appropriate CI classes, levels, attributes, and relationships to be used as part of a CMDB implementation. During a CMDB health check, ServiceNow examines the number of custom classes and attributes created and assesses whether these custom attributes are established at the correct level. ServiceNow provides a free store application called CMDB CI Class Models that can be installed on a ServiceNow instance to obtain a wide range of additional classes that are not provided in a base instance.

Automated discovery tools by SN: ServiceNow Discovery, Service Mapping, or Agent Client Collector

## Configuration and Asset Management Lifecycles

An asset becomes a CI (Configuration Item) when it is deployed and remains a CI throughout its lifecycle until it is returned to stock or disposed of. As illustrated in the diagram, Configuration Management and IT Asset Management are distinct, yet complementary practices.

## Change Control Board (CCB)

Form a Configuration Control Board (CCB). The CCB is a team of people that ensures your CMDB delivers continuous value. This team sets direction and makes decisions on what is needed to ensure your CMDB can support your organization’s strategic initiatives and determine if the CMDB is ready for utilization.

To operationalize and maintain the health of the CMDB, ServiceNow has created three of pillars to success. At the highest level each pillar focuses on a key customer pain point.

- First is Ingestion of CMDB data: This is how the CMDB is populated and the data is identified and reconciled. Automate as much as possible the flow of data into the CMDB at a frequency that supports your stated use cases
- Second is Governance of the data: Getting the data in is just the beginning of your CMDB journey. Next is the management and upkeep of the data to maintain a healthy CMDB and gain value from the data.
- Third is Insight into the data in the CMDB: How do you visualize and utilize this data across the platform?
## ServiceNow CMDB Data Population & Discovery Methods (Ingestion)

ServiceNow provides multiple approaches to populate and maintain the CMDB, ranging from automated discovery to integrations and data imports. Each method serves a specific purpose and has licensing and configuration considerations.

## ServiceNow Discovery (Horizontal / Agentless, IP-based discovery)

- Automatically discovers infrastructure (servers, network devices, applications).
- Populates the CMDB and maps dependencies between components.
- License: Paid (ITOM Visibility).
- Note: Discovered data should be enriched with non-discoverable attributes (e.g., support group, managed by).
- Schedule based; not real-time.
- It uses probes and sensors to determine the device type.
## MID Server:

- The MID Server (Management, Instrumentation, and Discovery Server) is deployed inside the organization’s trusted network.
- It acts as a secure bridge between the ServiceNow instance and internal systems that are not directly accessible due to firewalls or network restrictions.
- All communication between ServiceNow and the MID Server is encrypted.
- ServiceNow sends probes to the MID Server; the MID Server executes them and returns results, which sensors use to update the CMDB.
- Discovery is agentless and uses standard protocols:
- WMI for Windows
- SSH for Linux/Unix
- SNMP for network devices
- The MID Server ensures secure, scalable Discovery without exposing internal systems to the internet.
✔ Key takeaway: ServiceNow never directly connects to internal devices—everything goes through the MID Server.

## Discovery Schedules:

- Discovery Schedules define when, what, and where Discovery runs.
- Used for horizontal Discovery (network-based scanning).
- Specify:
- IP ranges / scope
- Schedule timing
- Assigned MID Server(s)
- Can target on-prem environments or cloud service accounts.
- Schedules trigger Discovery using probes, sensors, and patterns to identify and update CIs in the CMDB.
## Discovery Admin Workspace (Schedules Page)

- Central hub to monitor and manage Discovery operations.
- Provides real-time visibility into Discovery activity and performance.
- Key reports include:
## Schedules by location (map)

- Total schedules (last 24 hours)
## Errors by category

- Total Discovery attempts (completed vs canceled)
✔ Key takeaway: Discovery Schedules control horizontal Discovery execution and are monitored through the Discovery Admin Workspace.

## Types of Discovery:

- Network Discovery
- Identifies internal IP address ranges.
- Not required if IP ranges are already known.
- CI Discovery
- Discovers devices, servers, and applications.
- Most commonly used Discovery type.
## Cloud Discovery

- Discovers AWS and Azure resources.
- Uses cloud credentials and APIs.
## Serverless Discovery

- Discovers applications without discovering the host first.
- Pattern-based and does not rely on traditional host discovery.
✔ Key takeaway: All are forms of horizontal Discovery, each targeting different environments and use cases.

## Limiting Discovery Data:

- Improves data accuracy
- Avoids populating the CMDB with low-priority or irrelevant data.
- Establishes a strong foundation with high-quality CIs.
## Prevents CMDB data overload

- Reduces clutter caused by unnecessary Discovery results.
- Keeps the CMDB clean and maintainable.
## Faster initial deployment

- Fewer devices scanned → quicker Discovery cycles.
- Enables a usable CMDB early, with gradual expansion later.
## Simplifies CMDB management

- Focuses on key CI classes (e.g., servers, critical applications).
- Ensures data is immediately relevant to business needs.
## Better stakeholder buy-in

- Quick wins with accurate data build trust.
- Encourages support for broader Discovery adoption later.
✔ Key takeaway: Start small, discover what matters first, then expand Discovery incrementally.

## Discovery Ranges:

Discovery ranges define which IP addresses ServiceNow Discovery scans.

- You can include or exclude specific IP ranges in a Discovery schedule.
## Broad Ranges (Subnets)

- Example:
o 192.168.0.0/24

o 10.11.128.192/26

- Includes network and broadcast addresses.
- Scans a large number of IPs, which may cause:
- Data overload
- Redundant or irrelevant CIs
- Discovery errors
- Not recommended during initial implementation.
- Best practice: Do not exceed /16 (~65,000 IPs); split into smaller ranges if needed.
## Limited Ranges (Preferred Initially)

- Example:
o 192.168.0.1 – 192.168.0.254

o 10.11.128.193 – 10.11.128.254

- Excludes network and broadcast addresses.
- Targets specific, known devices.
- Improves data quality, performance, and troubleshooting.
- Supports clean and manageable CMDB growth.
✔ Key takeaway: Start with small, targeted IP ranges and expand Discovery gradually to avoid CMDB data overload.

## Discovery Configuration Console:

- Used to control what Discovery detects (devices, applications, software, and CIs).
- Allows including or excluding specific CI types from Discovery.
- Excluding a CI disables the related probe or classifier.
- Helps CMDB teams focus on principal CI classes only.
## Reduces noise, unnecessary data, and CMDB clutter.

### Access path: Discovery Definition → Configuration Console

✔ Key takeaway: Use the Configuration Console to limit Discovery to only the CIs you want to manage.

## Discoverable Data:

- Discoverable data is the hardware, software, and network information collected by ServiceNow Discovery.
- Common examples include:
- Hardware: CPU, memory, storage
- Software: operating systems, installed applications
- Network: IP address, MAC address, topology
- Cloud resources: AWS, Azure, Google Cloud
- Discovery runs on a scheduled basis to keep the CMDB up to date with infrastructure changes.
## Discovery Source Field

- Newly discovered CIs are created with Discovery source = ServiceNow.
- If a CI already exists (e.g., created via Asset Management), the source may initially be SNAssetManagement.
- Once discovered, the Discovery source is updated to ServiceNow.
### ✔ The Discovery source always reflects the last authoritative discovery method.

## Non-Discoverable Data:

- Non-discoverable data cannot be collected by automated tools like Discovery, Service Mapping, or Service Graph Connectors.
- Must be manually maintained or populated via automation after Discovery.
- Used to support ITSM processes such as Incident, Change, and Problem Management.
Common Non-Discoverable Fields

- Assigned to
- Owned by
- Support group
- Change group
- Managed by group
- Location
- Accurate group data is critical for:
- Proper incident routing
- Efficient change execution
- Operational accountability
✔ Key takeaway: Discovery populates technical CI data; CMDB admins must enrich CIs with non-discoverable ownership and group information.

## Service Mapping (Top-Down / ML-Powered, Tag-based discovery)

- Builds end-to-end service maps showing how business services are supported by IT components.
- Dynamically updates relationships as changes occur.
- License: Paid (ITOM Visibility).
- Note: Follow CSDM guidelines, define service owners, and relate services to business applications.
## Business Value:

- Bridges the gap between IT Operations and business users.
- Aligns IT service delivery with business outcomes, not just infrastructure.
- Supports ITSM processes: Incident, Problem, and Change Management.
## Key Concepts:

- Application Service: Logical representation of a deployed system, application, or product stack.
- Operational CI used in ITSM/ITOM practices.
- Can be environment-specific (Dev, Test, QA, Prod) or region-specific (AMS, EMEA, APJ).
- Stored in cmdb_ci_service_auto or sub-classes.
- Service Map: Shows which CIs support a service, including applications, servers, middleware, and networks.
- Helps identify service impact when components fail.
Types of Application Services

## Top-Down Mapping

- Pattern-Based:
- Best for: Mission-critical apps.
- Level: Surgical/Process-to-process.
- Key: Most Granular.
## ML Connection Suggestions:

- Best for: Homegrown & custom COTS.
- Level:  Traffic-based/Fingerprinting.
- Key: Fastest Time-to-Value.
- Note: These two can be used together or individually.
## Tag-Based Mapping

- Best for: Cloud-native, Containers, and VMs.
- Effort: Medium touch (requires defining tag categories/families).
- Key: Visualizes resource stacks across cloud infrastructure.
- Dynamic CI Group
- Best for: Small application services.
- Mechanism: Uses CI list filters or CMDB queries.
- Effort: High touch (requires manual query building).
## Key: No License Required.

Integration with CSDM:

- Supports Common Service Data Model (CSDM) by automating service and dependency modeling.
- Benefits include:
## Accurate service modeling

- Enhanced CMDB data quality
- Dependency management for impact analysis and operational support
## Benefits:

- Enhanced visibility of IT services and dependencies
- Faster root-cause analysis for incidents and problems
- Proactive, low-risk change management
- Improved compliance and governance through clear documentation
✔ Key takeaway: Service Mapping automates discovery and mapping of services and their dependencies, enabling IT teams to make informed decisions, reduce downtime, and improve service quality aligned with business objectives.

## Agent Client Collector (ACC – Agent-Based)

- Requires installing an agent on each host.
- Provides real-time endpoint visibility.
- Collects hardware, software inventory, configuration details, and software usage data (key for SAM).
- Configuration Details: Captures system configuration details, including OS settings, patch levels, and network configurations.
- License: Paid.
- Note: Agent deployment is mandatory.
Choose Agent Client Collector (ACC) when the scenario mentions:

- Laptops / workstations that are not always connected to the corporate network
- Remote users, VPN-based access, or devices that connect intermittently
- Security restrictions where the security team does not allow inbound scans or remote connections
- Highly secured / isolated networks (DMZ, restricted zones)
- Requirement to collect OS, software, processes, or security data directly from the endpoint
- Need for a single lightweight agent instead of multiple tools
## IntegrationHub ETL

- Automates extract, transform, and load processes into CMDB and other tables.
- Supports data normalization and scheduled automation.
- License: No (available via ServiceNow Store).
- Note: Requires good understanding of ServiceNow and source data models.
## Non-CMDB Table Support for IntegrationHub ETL

IH-ETL includes advanced functionality that allows data ingestion into non-CMDB tables.

A list of non-CMDB tables supported by default are specified in the system

property glide.identification_engine.non_cmdb_tables. These are the only tables that IH-ETL and IRE can work with. In addition, identification rules, including CI identifiers and identifier entries, must be created for these tables.

The following non-CMDB tables are supported in the latest release.

- Location [cmn_location]
- Department [cmn_department]
- Cost Center [cmn_cost_center]
- Building [cmn_building]
- User [sys_user]
- Group [sys_user_group]
The Discovery and Service Mapping Patterns application is a ServiceNow Store app.

New discovery patterns are released regularly through the ServiceNow Store, independent of major platform releases. This enables Discovery and Service Mapping customers to receive new or updated patterns without waiting for a full ServiceNow upgrade.

## Service Graph Connectors

- Pre-built integrations to sync data from external systems (e.g., Azure, InTune, MS SCCM, Jamf, AWS)
- Ensures CMDB data consistency across tools.
- Can automatically synchronize and update the CMDB in real-time or
on a scheduled basis, reducing manual data entry and improving efficiency.

- License: Paid (except SCCM connector, which is free).
Note: Requires credentials for target systems.

## Import Sets & Transform Maps (Legacy Method)

- Imports data from files, databases, or APIs into staging tables.
- Supports field mapping and transform scripts.
- License: No.
- Note: Does not use IRE by default, risking duplicates—recommended to enforce IRE via transform scripts.
Utilizing IRE during a CMDB Import:

- The Identification and Reconciliation Engine (IRE) centrally identifies and reconciles CI data from multiple sources, including manual imports.
- Identification rules are defined per CI class and consist of identifier entries (unique attribute sets with priorities) and related entries.
- By default, IRE is not used during imports. It must be explicitly enabled using a
custom onBefore script in the transform map.

- The CMDBTransformUtil API sends import set data to the IRE for identification before insert/update.
- IRE determines whether a CI is new or existing:
- New CI → Insert into CMDB
- Existing CI → Update the existing record
- When using CMDBTransformUtil, coalesce settings are ignored and are not required.
## Data Manager

Data Manager enables periodic certification and auditing of CMDB data to ensure accuracy and completeness.

- It uses scheduled certification policies that assign verification tasks to responsible users or groups.
## Two Methods to Auto-Populate Group Fields:

- CI Class Manager (Priority 2): Set Managed By Group at the CI class level; applies to all CIs in the class not linked to a Technology Management Offering.
- Technology Management Offering (Priority 1): Set Managed By, Support, and Change Groups at the offering level; applies to associated CIs and overrides CI Class Manager values.
Technology Management Offerings use dynamic CI groups behind the scenes to apply group values to their CIs.

CI Attribute Population Using Technology Management Offering

- Create a CMDB Group
- Create a Dynamic CI Group
- Create a Technology Management Service
- Create a Technology Management Offering
- Associate Dynamic CI Group to the Offering
- Automatic Group Synchronization
- System Business Rule (CSDM – Sync Group Attributes) syncs group values:
Service Builder is an alternative UI to achieve the same result, but it needs to be installed first from the ServiceNow store application.

## Management Tools Overview

CMDB Workspace

## CMDB Governance

- CMDB Health Dashboard
Monitors overall CMDB data quality through scorecards for Completeness, Correctness, and Compliance. It highlights top CI classes impacting health and allows drill-down analysis. Scheduled jobs must be manually activated for scorecards to populate.

## CMDB Health Dashboard:

Purpose: Provides a quick view of the overall quality of CMDB data using three key scorecards.

## Completeness

- Measures whether CIs have all required and recommended fields populated, including non-discoverable data (e.g., ownership, support group).
- Exam Tip: Missing essential data lowers completeness. Uses Recommended and Required metrics
ServiceNow does not provide predefined required or recommended CI attributes in the CMDB. These must be defined by the CMDB administrator and relevant stakeholders based on process requirements.

To prevent integrations (including Discovery and IRE) from failing due to missing mandatory CMDB attributes, ServiceNow provides two ways to override the default behavior:

## Via CMDB Properties UI

- Navigate to Configuration > CMDB Properties >
## Identification/Reconciliation Properties

- Find “Enforce the requirement that required attributes cannot be null during identification and reconciliation”
- Deselect the checkbox (set to false) and save.
- Via System Properties (sys_properties.list)
- Locate the property glide.required.attribute.enabled
- Set its value to false.
👉 Exam takeaway:

Both methods disable enforcement of required attributes during IRE identification and reconciliation, allowing integrations to proceed even when mandatory fields are missing.

## Compliance

- Shows how well CIs adhere to defined standards and audit policies. Uses Audit metric
- Exam Tip: Evaluates alignment with desired state configurations.
Compliance audits verify that CIs meet defined standards or policies. Typical examples include ensuring antivirus is installed, systems are patched to required levels, and mandatory ownership fields (such as Support Group and Managed by Group) are populated.

A common use case is system upgrades, where compliance audits identify servers that do not meet minimum hardware requirements (disk space, RAM, CPU) needed for the next upgrade. The Compliance Scorecard highlights non-compliant CIs so issues can be addressed before the upgrade.

## What Compliance Is Based On

- Audits comparing actual CI values vs expected values
- Expected values are defined via:
## Certification Templates

- Scripted Audits
## Common Audit Examples

- Antivirus installed on all workstations
- Linux servers on latest patch
- Production servers have Support Group and Managed by Group
- Hardware readiness for OS upgrades (RAM, disk, CPU)
### Key Rule (Very Important for Exam ❗)

✅ Only these audit types appear in the CMDB Health Dashboard Compliance Scorecard:

- Desired State audits
- Scripted audits
🚫 NOT included in the scorecard:

- Compliance
- Compliance Architecture
## Compliance Scorecard Configuration (4 Required Components)

### 1️⃣ Certification Filter

- Defines scope of the audit (which CIs)
- Based on CI class and conditions
- Examples:
- All Windows Computers
- All UNIX servers in a datacenter
- Navigation:
- CI Class Manager → Health → Compliance
- OR Compliance > Filters
### 2️⃣ Certification Template

- Defines conditions to pass the audit
- Can check:
- Attributes
- Relationships
- Reference fields
## Must reference a Certification Filter

- Audit type must be = Desired State
- Example:
- Windows Computers with RAM > 1000 MB
- Navigation:
- CI Class Manager → Health → Compliance
- OR Compliance > Templates
### 3️⃣ Audit

- Executes the comparison:
- Filtered CIs vs Template conditions
- Can:
- Be scheduled
- Create remediation tasks and assign It to a user or a group to work on It.
- Uses standard ServiceNow scheduler
- Navigation:
- CI Class Manager → Health → Compliance
- OR Compliance > Audits
### 4️⃣ Compliance Score Calculation Job

- Calculates Compliance KPI after audits run
- Scheduled Job:
## CMDB Health Dashboard – Compliance Score Calculation

- Navigation:
- Configuration > Health Preferences > Scheduled Jobs
- Must be:
## Activated

- Run by a user with admin role
- Status table:
- cmdb_health_metric_status
⚠️ If run by non-admin → inaccurate results

## Scripted Audits

- Used when templates are too restrictive
- Logic defined in script
- Still use:
- Certification Filter
- Included in Compliance Scorecard
- Cannot be created via CI Class Manager
- Navigation:
- Compliance > Desired State > Scripted Audits > Audits
- Base system includes sample:
- Data Center Zone Usage
### Desired State vs Data Manager (Exam Favorite 💡)

## CMDB Health Desired State Audits

- Automatic
- Ensures fields are:
- Present
- Configured correctly
- Example:
- Server has an owner and support group
## Data Manager Certification Policies

- Manual verification
- Used when data:
- Cannot be discovered automatically
- Generates certification tasks/checklists
- Example:
- Confirm Joe Smith is the correct owner of ServerXYZ
👉 They serve different purposes and are NOT the same

## Correctness

- Checks accuracy of CMDB data, including duplicates, outdated CIs, and proper relationships. Uses Duplicate, Orphan, and Staleness metrics
- Exam Tip: A CI passes correctness only if it meets all defined metrics. Score Calculation
- Overall percentage = % of CIs that pass all metrics, not an average of individual metrics.
- Example: Metrics: 93%, 100%, 96% → overall = 89% (because only 89% of CIs met all metrics).
## Duplicate CIs Definition

- Occurs when multiple CMDB records exist for a single real-world CI. Key Points
- Evaluated using predefined identification rules.
- Only independent CIs are evaluated (e.g., hardware, servers – not applications).
- Duplicates can be detected via:
- ServiceNow Discovery
- CMDB Correctness job
## Behavior

- A de-duplication task is automatically created.
- The oldest CI record (based on sys_created_on) is treated as the primary (non-duplicate).
- Newer records are marked as duplicates via the Duplicate Of field.
## Insights Provided

- Classes with the highest number of duplicates
- Discovery sources or CI owners causing duplication (root cause analysis)
## Orphan CIs Definition

- CIs that lack required relationships with other CIs.
## Key Points

- No base system orphan rules exist by default.
- Orphan tracking requires custom orphan rules.
- Only one orphan rule per class is allowed.
## Examples

- Application with no Runs on::Runs relationship to a server
- VM with no relationship to an ESX host
- Hardware CI with no owner
- Tomcat app with no relationship to a WAR file
## Impact

- Orphan percentage contributes to the overall Correctness Score.
## Stale CIs Definition

- CIs not updated within a defined time period. Base Rule
- Default staleness rule:
- Class: cmdb_ci
- Threshold: 60 days
- Applies to all child classes unless overridden
## How Updates Are Determined

- Based on sys_updated_on
- Even if no attribute changes occur, a discovery scan updates this field
## Custom Rules (Best Practice)

- Different CI classes can have different staleness thresholds:
- Network devices scanned every 14 days → staleness = 21 days
- Servers discovered daily → staleness = 7 days
## Why It Matters

- Prevents use of non-existent or outdated CIs
- Critical for lifecycle management and downstream processes
## Configuration & Governance

- CI Class Manager
- Used to configure Correctness Scorecard rules
- Supports:
- Duplicate identification
- Orphan rules
- Staleness rules by class
## Exam Takeaways (High-Probability Questions)

✅ Correctness Scorecard measures Duplicate, Orphan, and Stale CIs

✅ Duplicate metric applies only to independent CIs

✅ Oldest CI = primary, newer ones = duplicates

✅ No default orphan rules → must be configured manually

✅ Base staleness rule = 60 days at cmdb_ci

✅ sys_updated_on drives staleness calculation

✅ Metrics roll up into the CMDB Health Dashboard

## Manage & Remediate Duplicate CIs — Exam Notes

- What Are Duplicate CIs?
- Duplicate CIs = two or more CMDB records representing the same real-world item.
- They negatively impact:
- Incident, Change, and Problem Management
- Reporting & compliance
- Trust in CMDB data
## Common Causes of Duplicate CIs

Know these for scenario-based questions:

- Discovery tools (multiple tools discovering the same CI differently)
- Import Sets without proper identification rules
- Third-party integrations (REST/SOAP) without IRE logic
- Manual CI creation (poor governance, no naming standards)
## Incorrect or missing Identification Rules

- Lack of CMDB governance
## How ServiceNow Determines Duplicates

- Duplicates are detected by the Identification and Reconciliation Engine (IRE).
- IRE uses:
- Identification Rules → determine what uniquely identifies a CI
- Reconciliation Rules → determine which data source wins
- If multiple CIs match identification rules:
- A de-duplication task is created
- Visible in CMDB Workspace
⚠️ Important Exam Gotcha

- If duplicate CIs already have a Discovery Source populated, the CMDB Health Dashboard Correctness Scorecard will NOT flag them
- Once rediscovered and reprocessed by IRE → they will be flagged and a de-duplication task is generated
Duplicate CIs are only flagged by CMDB Health after they are processed by IRE — existing duplicates with a populated Discovery Source are ignored until rediscovery happens.

## Discovery Behavior with Duplicates

- When duplicates are found during Discovery:
- Oldest CI (by creation date) is updated
- Others are marked as duplicates
### Key Field Change (Important Update 🚨)

- Old: Discovery Source field was used to indicate duplicates
- New: Duplicate of field
- Reason:
- Preserve the Discovery Source with the last discovery tool
- Functionality remains the same
## De-duplication Tasks

- Created automatically when IRE detects duplicates
- Allow admins to:
- Review duplicate CIs
- Decide how to remediate them
Access:

- Legacy: De-duplication Tasks module
## Current: CMDB Workspace

## Duplicate CI Remediator

- Wizard launched from a de-duplication task
- Admin can:
- Select Main CI
- Merge attributes
- Maintain audit trail
- Supports:
- Merge
- Retain one CI
- Eliminate duplicates
## De-duplication Templates

Used for bulk remediation:

- Pre-configured remediation logic
- Applied:
- Per CI class
- In bulk
- Managed from:
- De-duplication Dashboard in CMDB Workspace
- Templates can be:
- Organized into libraries
- Executed on multiple de-duplication tasks at once
## System Properties for Duplicate Handling

Memorize these 🔑:

Behavior:

- If duplicates < threshold:
## Oldest CI is updated

- Others get Duplicate of populated
- IRE ignores CIs where Duplicate of is populated
## Now Assist for CMDB (AI-based)

Know what it does, not how to configure:

- Uses Generative AI
- Automates:
- Duplicate CI detection
- CI summarization
- Suggested remediation steps
- Works with:
- De-duplication templates
- CMDB Workspace
- Goal:
- Reduce manual effort
- Improve CMDB accuracy & governance
## Why Handling Duplicates Matters (Exam Framing)

- Ensures CMDB as a Single Source of Truth
- Improves:
- IT operations
- Reporting & compliance
- Decision-making
## One-Line Exam Summary

Duplicate CIs are identified by the IRE using identification rules, managed via de-duplication tasks in CMDB Workspace, remediated using the Duplicate CI Remediator or de-duplication templates, and flagged using the Duplicate of field—not Discovery Source.

## CI Reclassification & Restriction Rules — Exam Notes (Concise)

- CI Reclassification — Core Concepts
- Reclassification = moving a CI to another class during IRE identification
- Happens when CI data is placed in the wrong CMDB class
- Types:
- Upgrade → more specific (Server → Windows Server)
- Downgrade → less specific (Windows Server → Server)
- Switch → different branch (Linux Server ↔ Windows Server)
- Default behavior: automatic reclassification is enabled
Which of the following reclassification behaviors might cause Cl attributes and their data to be excluded during the reclassification process? [Choose two)

0	Upgrade

G	Downgrade

0	Promotion

G	Switch

Which results in a reclassification task being generated?

glide.class.downgrade.enabled set lo true and during discovery a Windows server is classified as a Linux server.

Correct

A reclassification task is generated only if the relevant reclassification property is set to false. For example, when a Server record is reclassified as a Windows server, it is considered on upgrade. Since the'glide.class.upgrade.enabled' property is set lo false. a reclassification task is triggered.

## Automatic vs Manual Reclassification

- Automatic enabled (default):
- CI is reclassified immediately
- Risk: data loss during downgrade or switch
## Automatic disabled:

- CI is not reclassified
- Reclassification task is created for admin review
## Base Reclassification System Properties

Enable automatic behavior:

- glide.class.upgrade.enabled
- glide.class.downgrade.enabled
- glide.class.switch.enabled Setting any to false:
- Prevents that reclassification type
- Creates a reclassification task
## Granular Control (Advanced IRE Properties)

These override legacy behavior:

- glide.identification_engine.update_without_upgrade_enabled
- glide.identification_engine.update_without_downgrade_enabled
- glide.identification_engine.update_without_switch_enabled Behavior when set to true:
## CI attributes are updated

- CI class is NOT changed
⚠️ These properties take precedence over glide.class.*

## Key Rule to Memorize

## Reclassification Restriction Rules

Purpose:

## Class-level control

- Prevent specific downgrades or switches
- Still allow attribute updates
Scope:

- Applies only to reclassification
## Does not block attribute updates

Location:

- cmdb_ire_reclassification_restriction.list
## Restriction Rule Behavior

Key fields:

- Type: Downgrade or Switch
## Source / Target table

- Inheritance flags:
- true → includes extended classes
- false → exact class only
## Exam Pattern: Inheritance Logic

- Source inheritance = true
- Rule applies to all child classes
- Target inheritance = false
- Rule applies only to exact target class
## Review Questions — Correct Answers

- Question 1 Config:
- glide.class.downgrade.enabled = true
- glide.identification_engine.update_without_downgrade_enabled = true
✅ Correct:

## Windows Server IS NOT allowed to be downgraded

- Windows Server CI attributes CAN be updated
## Question 2 Config:

- glide.class.downgrade.enabled = true
- glide.identification_engine.update_without_downgrade_enabled = false
- Restriction Rule:
- Type: Downgrade
- Source: Server (inheritance = true)
- Target: Computer
✅ Correct:

## Windows Server IS NOT allowed to be downgraded to Computer

- Windows Server CI attributes CAN be updated
## Question 3

Config:

- Same restriction rule as Q2
### CI: IP Router → Network Gear

✅ Correct:

## IP Router IS allowed to be downgraded

- IP Router CI attributes CAN be updated
(Restriction applies only to Server and its child classes)

One-Line Memory Hook:

CMDB Health = Completeness (fields), Compliance (standards), Correctness (accuracy), overall % = CIs passing all metrics.

Health Inclusion Rules:

- Purpose: Define which CI classes are evaluated by the CMDB Health Dashboard
(Correctness, Completeness, Compliance).

- Why needed: Discovery tools can populate large volumes of CIs; not all are owned or managed by the organization.
- Best practice: Include only CI classes your organization is responsible for to ensure meaningful and performant health metrics.
## Key Capabilities:

- Selective Class Tracking: Limit health calculations to relevant CI classes.
- Metric-Level Control: Apply rules to specific metrics (e.g., Correctness only).
- Customizable Scope: Include or exclude CI types based on operational responsibility.
- Class Hierarchy Support: Use operators like “is a” to include parent classes and all extended child classes.
## Key Exam Tip:

- Health Inclusion Rules are the first step in filtering CMDB data for the Health Dashboard.
## CMDB Group Health Dashboard:

- Provides an aggregated health view of CIs within a CI group.
- Shows Correctness, Completeness, and Compliance with drill-down to issues like
## missing fields, audits, duplicates, orphans, and stale CIs.

- Eliminates the need to switch between individual CI classes.
## Steps to configure CMDB Health Metrics

- Configure Staleness, Orphan, Required, Recommended in CI Class Manager
- Task creation is OFF by default (except de-duplication)
- Enable tasks:
### CMDB Health Dashboard > Settings → Health Preferences → Health Metrics

- Select metric → Create Task = ON
- Assign group and save
- Run CMDB Health jobs to update dashboard and create tasks
- Job status table: cmdb_health_metric_status
## CMDB Health Remediation:

- Applies to Orphan CI, Stale CI, Required & Recommended fields
- Enable task creation per metric:
### Health Preferences → Health Metrics → Create Task = ON

- CMDB Remediation Rule links the metric to the workflow
- CMDB Health Jobs run → remediation tasks are created
## Exceptions (must remember):

- De-duplication → tasks auto-created
- Compliance audit → configured in CI Class Manager, not via this flow
## Life Cycle Management (flow):

## CI & Asset Life Cycle Synchronization:

- CIs and Assets share fields (e.g. Serial Number, Model, Assigned to) to keep data consistent.
- Legacy life cycle fields still widely used:
- CI: Install Status, Hardware Status, Operational Status
- Asset: State, Substate
- Do NOT manage all legacy fields → choose one (e.g. Install Status or Hardware Status).
CSDM Life Cycle Fields (Recommended)

## Life Cycle Stage

- Life Cycle Stage Status
- Introduced to standardize life cycle status and align with CSDM best practices.
## Synchronization Key Points

### Asset ↔ CI auto-creation supported in base system.

- Shared fields sync via Asset–CI Field Mappings table.
## Legacy life cycle sync is directional

(e.g. Asset State → CI Install Status, not always vice versa).

## Life Cycle Mapping

- Life Cycle Mapping table (life_cycle_mapping) maps legacy values → CSDM values.
## Enable Life Cycle Sync:

- One-time sync of legacy → CSDM fields
- Shows Discrepancy Report for unmapped values
- After enabling:
- Legacy fields ↔ CSDM fields stay synchronized
- Install Base Item (IBI) also stays in sync
### One-line exam takeaway □

## CSDM Life Cycle fields standardize status, legacy fields still exist, and ServiceNow auto-syncs CI, Asset, and IBI via mapping tables.

- CMDB Data Manager
Manages the CMDB data lifecycle and governance. It supports data certification, lifecycle policies (retire, archive, delete), and attestation policies to validate the existence of infrastructure and applications. Some lifecycle actions require active lifecycle rules per CI class.

## Duplicate CI Remediation Wizard

Identifies and helps resolve duplicate CIs using guided, manual workflows. It supports

merge or delete actions but requires user effort for each de-duplication task.

## De-Duplication Templates

Enable automated, bulk de-duplication using configurable matching rules (e.g., class, model, manufacturer). Templates can be scheduled to regularly merge or delete duplicates, but thorough testing is strongly recommended before activation.

# CMDB Insight

## CMDB Query Builder

Enables users to visually build complex queries across CMDB and non-CMDB tables using a drag-and-drop interface. It supports advanced filtering with AND/OR logic but requires a good understanding of the ServiceNow data model and CI relationships.

## Unified Map

Provides an interactive visual map of CIs and their relationships, helping users understand dependencies and assess the impact of changes or incidents.

```javascript
Effective use depends on understanding service-to-infrastructure mappings.
```

Accessible from CMDB Workspace.

The Unified Map combines: Application Service and Dependency View

## Intelligent Search

Enhances CMDB search using natural language queries (NLQ) powered by AI. It improves usability by reducing the need for deep technical knowledge while still supporting advanced filtering.

## CMDB and CSDM Data Foundations Dashboards

Offer visibility into CMDB data quality and alignment with CSDM standards, monitor policy compliance, and provide playbooks with best-practice guidance. Updates may be required via the ServiceNow Store.

The remediation playbooks are knowledge articles on the ServiceNow support site that provide context for the respective issue. Each playbook is quite detailed providing a summary of the indicator, an overview of the problem, and why it is important to address the issue.

## CI Class Manager

The CI Class Manager is a centralized tool in ServiceNow for managing CMDB CI classes and their hierarchy. It provides a tree-view to easily navigate class relationships and understand parent–child dependencies. Through this manager, administrators can create, view, and update CI classes, define attributes, and configure identification and reconciliation rules to improve data accuracy and consistency.

```javascript
It also supports CMDB health and compliance by enabling audits, certification filters, templates, and mandatory/recommended field settings. Additionally, it allows extensibility by creating new child classes or modifying existing ones.
```

The Basic Info tab lets you configure core class details such as the Display Name and control whether the class is extensible, while the Attributes tab focuses on managing class fields and their behavior.

## Principal Class

A Principal Class is a designation assigned to a CI class in the CMDB. When a class is flagged as principal:

- ITSM processes are streamlined by filtering which CIs appear in the “Configuration Item” reference field in records like incidents, problems, and changes.
- Only relevant CIs from the designated class are shown, simplifying selection for users.
Example: Marking the “Servers” class as a Principal Class ensures only server-related CIs appear in ITSM records, reducing clutter and improving efficiency.

- Managed by group value can be configured through the technical service offering. If It's set there, It will take precedence over the value set In the CI class Manager.

---

## Identification Rules

Identification Rules are used to uniquely identify Configuration Items (CIs) within the CMDB, ensuring each CI is recognized and managed correctly.

- They rely on identifier entries, which define the unique attributes used for identification.
- Common attributes include Name, Serial Number, Device ID, Object ID, Configuration File, Version, and others.
- A CI is considered unique when the defined combination of attributes matches.
## Example:

A CI may be uniquely identified using Class + Configuration File + Version. Allow Null Attributes

When enabled, a match is attempted as long as at least one criterion attribute has a value, even if other attributes are null.

## Allow fallback to parent's rule

Allows the identification rules of the Cl's parent to be used if a match is not found.

Dependent Relationships

Dependent relationships describe how one CI relies on another within the IT environment, helping teams understand dependencies and potential impacts.

## Key benefits include:

- Dependency Mapping: Shows how CIs are connected (e.g., an application depends on a server).
- Impact Analysis: Enables quick assessment of affected services during outages or changes.
- Lifecycle Management: Ensures lifecycle changes (such as decommissioning) are handled correctly for all dependent CIs.
Override Dependent Relationship Rule types. Here’s a simple explanation:

## Hosting

- Used for direct hosting relationships.
- Only one level deep.
- Typically involves physical or virtual resources.
- Example:
Server hosts Application

Containment

- Used for grouped or hierarchical relationships.
- Relationships are chained together.
- One CI type acts as the top-level (root) parent.
- Example:
Data Center → Rack → Server

## In short:

- Hosting = direct, one-to-one hosting
- Containment = hierarchical, parent–child grouping
## Reconciliation Rules

Reconciliation rules control how CI data is updated in the CMDB by defining which data sources are allowed to update specific CI attributes and in what priority order. They are configured in the CI Class Manager and help maintain data integrity and consistency.

- Authorize specific discovery or data sources to update CI fields.
- Prevent lower-priority or unauthorized sources from overwriting trusted data.
- Resolve conflicts when multiple sources attempt to update the same CI attributes by applying source priority.
## Data Refresh Rules

Data refresh rules define when CI attributes can be refreshed if a higher-priority data source has not updated the CI within a specified timeframe. This ensures data remains current without compromising source authority.

Suggested Relationships are predefined recommendations that guide users in creating logical and meaningful relationships between CIs in the CMDB.

They help ensure relationships are accurate and make sense operationally.

## Examples:

- Provides Power for :: Receives Power From
→ A rack provides power for a server.

## Runs on :: Hosts

→ A database runs on a server.

Illogical relationships (e.g., a rack runs on a server or a server runs on a database) are avoided.

---

## Health

The Health tab lets you configure KPIs and metrics to monitor CMDB data quality. Health is measured using three KPIs:

- Completeness: Required and recommended CI fields are populated.
- Compliance: CIs adhere to defined audits.
- Correctness: CIs meet data integrity rules, identifying duplicates, orphaned, or stale CIs.
Results are aggregated at the CI class level and then at the overall CMDB level. Health Inclusion Rules define which CIs are included in these calculations.

## IRE

The Identification and Reconciliation Engine. The IRE is crucial and a central component to ingesting healthy data into the CMDB. It ensures accurate and consistent data by identifying and reconciling configuration items (CIs) from multiple data sources. The IRE helps maintain the integrity of the CMDB by reducing duplicate CIs and controlling updates to CIs when multiple data sources, such as Discovery, Service Mapping, Service Graph Connectors, and REST integrations are used to create and update CI records.

In addition, once data is present in the CMDB, ServiceNow provides multiple management tools to view, analyze, report on, visualize, and remediate data in the CMDB. These various management tools are covered later in the course.

## IRE Features:

- Identification: Uniquely identifies Configuration Items (CIs) using identification rules to determine whether a CI already exists in the CMDB or needs to be created.
- Reconciliation: Controls how CI data is updated by allowing only authorized data sources to write to specific CI tables and attributes, ensuring accurate and prioritized data.
- De-duplication: Detects and groups duplicate CIs into de-duplication tasks, enabling review and cleanup using built-in tools like wizards and templates.
- Reclassification: Flags cases where a CI should change its class (upgrade, downgrade, or switch) and creates a task for manual review if automatic reclassification is disabled.
The IRE provides centralized APIs used by discovery and integration tools to enforce identification and reconciliation before data is written to the CMDB. This prevents direct CMDB updates, ensuring data consistency by avoiding duplicates and blocking updates from unauthorized sources.

Both issues occur when CI identification attributes do not accurately represent a CI’s unique identity:

- Duplicate CIs: Multiple CMDB records represent the same CI due to weak or changing identification rules that fail to uniquely identify each CI.
- Overloaded CIs: Different CIs are mistakenly identified as one, resulting in a single CMDB record where multiple CIs should exist.
Default rules for Hardware and Application:

- Hardware Rule: Default identification rule for all hardware CIs, applying to the Hardware table and its extended classes, such as Server, to manage inserts and updates in the CMDB.
- Application Rule: Default identification rule for application CIs, applied at the Application table level and used when no more specific rules exist for extended application classes.
ServiceNow provides hundreds of rules out-of-the-box to assist with the identification process.

Criterion attributes are the fields that uniquely define a CI during the IRE identification process. The OOB setup differs from one table / class to another.

Allow null attribute when set to false means all criterion attributes must have values to attempt matching with an identifier entry.

For an identification rule to be effective, it must meet these two conditions:

- The criterion attributes must uniquely identify the CI (for example, serial number, host name, or install directory).
- The criterion attributes must remain unchanged throughout the CI’s lifecycle; attributes that can change over time (such as IP address) should not be used.
If additional rules need to be created beyond the default application identification rules, it is recommended to create good rules that are set with the highest priority for the strongest identifier entries that do not change over time.

Software applications often lack a unique serial number, so they are best identified by how they run and where they are installed. Because multiple instances of the same application can run on a single host with the same name, using the installation directory or configuration file path or running process command is a best practice. These attributes remain unique for each instance, even on the same machine, making them effective and reliable identifiers.

"Path not name"

## System property set to true

An Advanced Options section on non-lookup identifier entries becomes available. The Advanced Options section allows the CMDB administrator the ability to set optional conditions to narrow the set of records that will be searched for a matching CI.

## IRE Support for Non-CMDB Tables:

IRE supports a limited set of base non-CMDB tables to improve data quality by enforcing identification rules. Supported tables include Location, Department, Cost Center, Building, User, and Group. CI Class Manager is not used; identification rules are created directly on the tables via list views, with one rule allowed per table.

## Reconciliation Rule How to Prevent Inserts?

Reconciliation rules help prevent updates from unauthorized or unwanted sources or lower-priority sources from overwriting data provided by higher-priority sources, focusing specifically on updates.

To further refine control and block inserts from a specific data source, a CMDB administrator can configure IRE Data Source Rules by navigating to: Configuration > Identification/Reconciliation > IRE Data Source Rules.

When multiple data sources can update the same CI class or attributes, reconciliation rule prioritization determines which source is authoritative. This prevents authorized sources from overwriting each other’s data and ensures a clear source of truth.

The Data Source Histories [cmdb_datasource_last_update] table in ServiceNow is used to track the last update time for each data source that contributes data to the Configuration Management Database (CMDB). This table is populated only after reconciliation rules are configured for a specific class and data is ingested into that class.

## CMDB 360 / Multisource CMDB

Before the Paris release, ServiceNow CMDB could track only the last data source that updated a CI or its attributes, stored in the Data Source Histories (cmdb_datasource_last_update) table. When multiple discovery sources reported values for the same attribute, lower-priority values were discarded by reconciliation rules, making it difficult to analyze data conflicts, compare sources, identify gaps, or improve reconciliation logic.

After the Paris release, Multisource CMDB, available through CMDB 360 in CMDB Workspace, was introduced. It retains full attribute-level history from all discovery sources—both accepted and rejected values—stored in the CMDB MultiSource Data (cmdb_multisource_data) table.

This enables CMDB administrators to track how each CI is populated, compare values across sources, revert updates from specific sources, recompute attributes after reconciliation rule changes, and better assess data quality and source coverage using CMDB 360 analytics and queries.

## CMDB 360/Multisource CMDB solves the following:

- Inability to store all CI data ingested by various discovery sources
- Inability to find the reported value from multiple discovery sources
- Inability to remove and replace data from an incorrect discovery source
- Inability to modify reconciliation rules and recompute the data immediately
Multisource data can be accessed from a CI record under the Related Links or CI Class Manager from the Reconciliation Rule tab.

The data under the CMDB 360 view populates each day after the following scheduled job

executes:

- Multisource Dashboard Analytics Population
How to enable Multisource CMDB:

Activate the ITOM Discovery License (com.snc.itom.discovery.license) plugin.

Navigate to All > Configuration > CMDB 360 Properties. Then, in the CMDB 360 Properties pane ensure that the glide.identification_engine.multisource_enabled (Enables CMDB 360) property is set to true.

CI Class Manager (Recompute)

Use the recompute option to recalculate CI attribute values when reconciliation rules are modified or a discovery source is found to be invalid. This ensures the updated rules or sources are correctly applied.

## CMDB 360 Query

CMDB 360 Query is a powerful feature that helps customers explore and analyze CMDB data to answer critical operational questions. It provides three main query options:

- Explore 360 Data: Understand what CI data is being reported and by which discovery sources, enabling deep visibility into attribute-level data.
- Identify Data Mismatches: Detect inconsistencies when multiple data sources report different values for the same CI attribute.
- Gap Analysis: Identify missing or inconsistent discovery coverage, such as when one source reports a CI and another does not.
Using CMDB 360 Query, administrators can easily find issues like servers missing the ServiceNow Agent Client Collector or Windows servers not discovered by ServiceNow Discovery. Overall, this feature improves CMDB transparency, data quality, and confidence in discovery sources.

Dynamic Reconciliation Rules

The Dynamic Reconciliation Rule option is only available after the Multisource CMDB is enabled.

When both static and dynamic reconciliation rules apply to the same CI attribute, the

dynamic reconciliation rule takes precedence.

## Dynamic reconciliation rules support several rule types such as:

- First Reported
- Most Reported
- Last Reported
- Largest Value
- Smallest Value
The largest and smallest value types only apply to numeric field types. When on the Select Attributes tab of the Create Reconciliation Rule wizard, only numeric field types are displayed, and the other attributes are hidden.

## Key Points to Remember

- Dynamic Rules defined within a specific class take precedence over rules defined from a parent class.
- If no rules are defined for a specific class, rules defined at a parent class apply.
- If the same CI attribute has both, a static reconciliation rule and a dynamic reconciliation rule, the dynamic reconciliation rule takes precedence.
The Server class uses a dynamic reconciliation rule that selects the largest value for the RAM field, while the Windows Server class uses a rule that selects the most reported value. Based on the RAM values available from different discovery sources in the Multisource CMDB for a given Windows Server, which RAfv\ value will ultimately be written to the CMDB for that Windows Server record?

### Tivoli RAM: 40961ServiceNow RAM: 4096 I LANDesk RAM: 2048 I Altiris RAM: 6020

### Corl'ecl

4096 is the correct answer since it is the most reported value for the Windows Server class as configured in the dynamic reconciliation rule.

The Server class usesa dynamic reconciliation rule that selects the largest value ior the RAM field, while the Windows Server classusesa rule that selects the most reported value. Based on the RAM valuesavailable from different discovery soUTces in the Muttisource CMDB lot a given Server, which RAM value will uttimately be written to the CMDB for that Server record?

- Tivoi RAM: 4096 I ServiceNow RAM: 4096 I WJDe,k RAM: 2048 IAttiris RAM: 6020
### Conect

The dynamic rule for the Server class specified "large:.st value _ 6020 is the highest value in

### the multisource CMDB.

Business Services, Technology Management Services, Business Service Offerings, and Technology Management Offerings can be created using forms and llsts or In a more streamllned manner using which of the followlng?

- . Application Service Wizard
- Service Mapping
- CMDB Worl<space
- Service Builder
- .Cl Class Manager
In ServlceNow, which of the followlng are potenllal consequences of not allgnlng with the Common Service Data Model (CSDM)?

[ Choose 2 answers]

- Potential loss of data
- Incompatibilitywith future ServiceNow products
- Increasedtechnical debt
- Inability to install ServiceNow store applications
Which CSDM domain are business appllcallons, Information objects, and capabllltles part of?

- Design & Planning
- Build & Integration
- service Delivery
- Service Consumption
Which CSDM domain represents deployed service Instances and their related, dlscoverable, components?

- Service Consumption
- Design & Planning
- service Delivery
- Build & lntegra□on E_ Ideation & Strategy
### What are the 3 plllars to focus on to achieve a successiful data foundation?

I Choose 3 answers]

- Gompliance B..lrigeSl
### C. Completeness D.Govern

### E. Correotness

### F. lnsighl

Which feature can be used to relate an appllcatlon service/service Instance with a technology management ol'ferlng, business service offering, and/or a business appllcatlon?

A. Service Bullder

B. lntegrationHub ETL C CMDB Workspace

- Application Service Wiza
- .Cl Class Manager
### Which CSDM domain Is Customer �rvlce Management par,t of?

- S81"Vice Delivery
- Ideation & Strategy
- Build & Integration
- Design & Planning
- Sel\lice Consumption
Which of the following provides a unlHed workspace that allows owners to hollsllcally view and collectively manage their portfolios, services, offerings, and products through the full llfecycle?

- CMDB Workspace
- Service Buik:ler
- Service Operations Workspace
- Digital Portfolio Managemenl
- Cl Class Manager
Which Held(s) does CSDM recommend lo use lo manage the life cycle of a ConHgurallon Item (Cl)?

- Hardware status
- Install StalUS
- Life cycle stage and stage status
- Operational status
Which Is a service Instance type that Is a loglcal representation or a deployed application stack and Its dependencies?

- Business Application (andb_ci_business_app]
- Application Service [cm<lb_ci_service_auto]
c.Applk:atlon (cmdb_ci_appl]

D. Technology Management Service [cmdb_ci_service_technical]

Which ServlceNow feature Is a built-In visualization and reporting tool that helps organizations assess and Improve their lmplementallon of the Common Service Data Model (CSDM) based on ServlceNow suggested good practices?

- Cl Class Manager
- CMDB Health Dashboard
- CSDM Data Foundations Dashboard
- Application Service Wizard
- Service Builder
Which of the following are operational ConHguratlon Items (Cls) that can be selected and populated In the ConHguratlon Item Held on an Incident or Change Request record?

[ Choose 2 answers ]

- Installed sortware
- Business Application
- Dynamic Cl Group
- Application service
From which of the following can the Managed by group be conHgured and synchronized to the underlying group or class of ConHguratlon Items (Cls)?

[ Choose 2 answers ]

- Technology Managemem Orterings B.Technology Management Services
C. Cl Class Manager

D. Business Service Offerings

E. Business services

### Which CSDM domain Is an enterprise architect Involved In?

### A ldealfon & Stralegy

### .Service Consumption

- Sel'\lice Delivery
- BuHd & Integration
- Design & Planning
Aligning to the Common Service Data Model (CSDM) allows for auto populallon of the assignment group Held on new Incident and change request records. Which of the following are true when creating a new Incident or Change Request In ServlceNow?

[ Choose 2 answers]

A. Change group on the selected er auto-populates the assignmem group neld on the change request form.

B. Managed by group on the selecred Cl auro-populates the assignment group neld on the lnck:Jem form. c_support group on the .selecred Cl auto-populates the assignment group fleld on the Incident form.

D. Approval group on the selected Cl auto-populares the assignment group fleld on rhe change requf!:SI form

Quick Study Guide

To keep the domains straight, try these mental shortcuts:

Domain	Mental Anchor	Key Keywords

Ideation & Strategy	The 0Goal0Business Capability, Business Unit

Design & Planning	The 0Blueprint"	Business Application, Information Object

Build & Integration	The °CreationM	SDLC, DevOps, Microservices

Service Delivery	The 00perationM Application Service, Discovery, Infrastructure

Service Consumption The "ExchangeM  Catalog, CSM, Portfolio, Request


| Property | Purpose |
|---|---|
| glide.identification_engine.skip_duplicates | Skips duplicates (default: true) |
| glide.identification_engine.skip_duplicates.threshold | Max duplicates allowed (default: 5) |



| Scenario | CI Class | CI Attributes |
|---|---|---|
| update_without_* = true | ❌ Not changed | ✅ Updated |
| update_without_* = false | Depends on rules | Depends on rules |



| @ | 6020 |
|---|---|
| @ | 2048 |
| G | 4096 |
| @ | 1024 |



| 0 | 6020 |
|---|---|
| 0 | 2048 |
| 0 | 4096 |
| 0 | 1024 |

