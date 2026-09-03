The CMDB is the database while the Common Service Data Model (CSDM) is the data model. The data model helps determine where to record items in the CMDB, and what relationships are important to drive business value.

## Configuration Item (CI)

Physical and logical components of an infrastructure that needs to be managed to deliver a product or service and are currently, or soon will be, under configuration management. For example, a network device, a server, an application, a delivery truck, or service.

## Attribute

Information that further describes a CI such as a name, serial number, manufacturer, operating system.

Relationship Type

Include the relationships between configuration items. For example, a web application might read data from a specific database, which in turn might depend on a piece of underlying hardware.

Class

Describes a table that contains and represents a specific type or group of CIs that share common attributes such as a Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, Animal etc.

Configuration Management Database (CMDB)

A database used to store configuration records throughout their Lifecycle. The Configuration Management System maintains one or more CMDBs, and each CMDB stores attributes of CIs, and Relationships with other CIs.

## Base Table

The core Configuration Item [cmdb_ci] table, which stores the basic attributes of all the CIs. All configuration item classes extend from this table including all hardware and applications.


## CI Reclassification

Is a CI whose class has been upgraded, downgraded, or switched. An example of an upgraded CI is a Server record that was upgraded from the Server [cmdb_ci_server] class to the Windows Server [cmdb_ci_win_server] class.

## Parent and Child Class

A table that extends another table is called a child class, and the table it extends is the parent class. A table can be both a parent and child class both extending and providing extensions for other tables. For example, the Server table extends the Computer table and the Windows Server table extends the Server table, thus making the Server table both a Parent and Child class.

## Asset vs. CI

On the Now platform, when creating a hardware asset, a corresponding CI will be automatically created or when a CI is discovered for the first time and inserted into the CMDB, a corresponding asset record will be automatically created. The asset and the CI is connected through out the CI/Asset lifecycle.

## Asset:

- Often starts during the procurement process, but may be created when a discovery tool finds the CI for the first time

- Is part of the financial lifecycle

## Configuration Item (CI):

- Often starts when a discovery tool finds the CI for the first time, but may be created during the procurement process

- Is part of the technical operations

## Common Services Data Model (CSDM)

Represents a standard and shared set of service related definitions across ServiceNow products and the NOW platform that enables and supports true service level reporting while providing prescriptive guidance on service modeling within the CMDB. These service-related definitions span the ServiceNow® product portfolio and the Now Platform®.

## Application Service

A set of interconnected applications and hosts which are configured to offer a service to the organization. Application services can be internal, like an organization email system


or customer-facing, like an organization website.

## Application

Applications that comprise an application service as configuration items (CIs). The various Applications and the relationships between them, that comprise an application service, are stored in the CMDB. (i.e. Tomcat, Apache, Microsoft SQL, Oracle, IIS).

## DevOps

Consists of developers who build applications and the operations groups who deploy and maintain them within an enterprise. In a DevOps environment, these two groups are combined into one in order to work more effectively together to accelerate and improve service delivery.

## Principal Class

Principle Classes can be configured to limit the CI classes that display in the Configuration Item fields on incident, problem, and change records.

## Logical CI

Do not take up space. They perform specific functions requiring physical components in order to operate. Examples include Service Offering, Service, Business Application which are manually entered into the CMDB.

## 1 1️⃣ Business Application

- Logical CI: 
Microsoft Teams
 (the collaboration/chat app used by employees)


## Physical CIs it depends on:

- o Cloud servers hosting Teams

- o Network infrastructure (routers, switches)

- o Databases storing user info and messages

## 2 2️⃣ Service

- Logical CI: 
Corporate Email Service

- Physical CIs it depends on:

- o Exchange Server or Office 365 backend

- o Mail servers

- o Storage for email data

- o Network connections for email delivery

## 3 3️⃣ Service Offering

- Logical CI: 
VPN Access for Remote Employees

- Physical CIs it depends on:

- o VPN servers

- o Firewalls

- o Network links to the corporate office

## 4 4️⃣ Other Examples

- Logical CI: 
HR Payroll System

- o Depends on: Payroll application servers, database servers, authentication servers.

- Logical CI: 
Customer-Facing Website

- o Depends on: Web servers, application servers, load balancers, content delivery network.

Logical CI = What the business sees / uses Physical CI = What actually runs it behind the scenes

Foundation data:


Not part of the CMDB, but referenced In the CI records.

One of the most important and challenging aspects of CMDB design is selecting the appropriate CI classes, levels, attributes, and relationships to be used as part of a CMDB implementation. During a CMDB health check, ServiceNow examines the number of custom classes and attributes created and assesses whether these custom attributes are established at the correct level. ServiceNow provides a free store application called CMDB CI Class Models that can be installed on a ServiceNow instance to obtain a wide range of additional classes that are not provided in a base instance.

Automated discovery tools by SN: ServiceNow Discovery, Service Mapping, or Agent Client

Collector


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

## 1. ServiceNow Discovery (Horizontal / Agentless, IP-based discovery)

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

- o WMI for Windows

- o SSH for Linux/Unix

- o SNMP for network devices

- The MID Server ensures secure, scalable Discovery without exposing internal systems to the internet.

Key takeaway: ServiceNow never directly connects to internal deviceseverything goes through the MID Server.

## Discovery Schedules:

- Discovery Schedules define when, what, and where Discovery runs.

- Used for horizontal Discovery (network-based scanning).

- Specify:


- o IP ranges / scope

- o Schedule timing

- o Assigned MID Server(s)

- Can target on-prem environments or cloud service accounts.

- Schedules trigger Discovery using probes, sensors, and patterns to identify and update CIs in the CMDB.

## Discovery Admin Workspace (Schedules Page)

- Central hub to monitor and manage Discovery operations.

- Provides real-time visibility into Discovery activity and performance.

- Key reports include:

- o Schedules by location (map)

- o Total schedules (last 24 hours)

- o Errors by category

- o Total Discovery attempts (completed vs canceled)

Key takeaway: Discovery Schedules control horizontal Discovery execution and are monitored through the Discovery Admin Workspace.

## Types of Discovery:

- Network Discovery

- o Identifies internal IP address ranges.

- o Not required if IP ranges are already known.

## CI Discovery

- o Discovers devices, servers, and applications.

- o Most commonly used Discovery type.

- Cloud Discovery

- o Discovers AWS and Azure resources.

- o Uses cloud credentials and APIs.

## Serverless Discovery

- o Discovers applications without discovering the host first.

- o Pattern-based and does not rely on traditional host discovery.

Key takeaway: All are forms of horizontal Discovery, each targeting different environments and use cases.


## Limiting Discovery Data:

- Improves data accuracy

- o Avoids populating the CMDB with low-priority or irrelevant data.

- o Establishes a strong foundation with high-quality CIs.

- Prevents CMDB data overload

- o Reduces clutter caused by unnecessary Discovery results.

- o Keeps the CMDB clean and maintainable.

- Faster initial deployment

- o Fewer devices scanned → quicker Discovery cycles.

- o Enables a usable CMDB early, with gradual expansion later.

- Simplifies CMDB management

- o Focuses on key CI classes (e.g., servers, critical applications).

- o Ensures data is immediately relevant to business needs.

- Better stakeholder buy-in

- o Quick wins with accurate data build trust.

- o Encourages support for broader Discovery adoption later.

Key takeaway: Start small, discover what matters first, then expand Discovery incrementally.

## Discovery Ranges:

Discovery ranges define which IP addresses ServiceNow Discovery scans.

- You can include or exclude specific IP ranges in a Discovery schedule.

- Broad Ranges (Subnets)

- Example:

- o 192.168.0.0/24

- o 10.11.128.192/26

- Includes network and broadcast addresses.

- Scans a large number of IPs, which may cause:

- o Data overload

- o Redundant or irrelevant CIs

- o Discovery errors

- Not recommended during initial implementation.

- Best practice: Do not exceed /16 (~65,000 IPs); split into smaller ranges if needed.


## Limited Ranges (Preferred Initially)

- Example:

- o 192.168.0.1 – 192.168.0.254

- o 10.11.128.193 – 10.11.128.254

- Excludes network and broadcast addresses.

- Targets specific, known devices.

- Improves data quality, performance, and troubleshooting.

- Supports clean and manageable CMDB growth.

Key takeaway: Start with small, targeted IP ranges and expand Discovery gradually to

avoid CMDB data overload.

## Discovery Configuration Console:

- Used to control what Discovery detects (devices, applications, software, and CIs).

- Allows including or excluding specific CI types from Discovery.

- Excluding a CI disables the related probe or classifier.

- Helps CMDB teams focus on principal CI classes only.

- Reduces noise, unnecessary data, and CMDB clutter.

- Access path: Discovery Definition  Configuration Console

Key takeaway: Use the Configuration Console to limit Discovery to only the CIs you want to manage.

## Discoverable Data:

- Discoverable data is the hardware, software, and network information collected by ServiceNow Discovery.

- Common examples include:

- o Hardware: CPU, memory, storage

- o Software: operating systems, installed applications

- o Network: IP address, MAC address, topology

- o Cloud resources: AWS, Azure, Google Cloud

- Discovery runs on a scheduled basis to keep the CMDB up to date with infrastructure changes.

- Discovery Source Field

- Newly discovered CIs are created with Discovery source = ServiceNow.


- If a CI already exists (e.g., created via Asset Management), the source may initially be SNAssetManagement.

- Once discovered, the Discovery source is updated to ServiceNow.

The Discovery source always reflects the last authoritative discovery method.

## Non-Discoverable Data:

- Non-discoverable data cannot be collected by automated tools like Discovery, Service Mapping, or Service Graph Connectors.

- Must be manually maintained or populated via automation after Discovery.

- Used to support ITSM processes such as Incident, Change, and Problem Management.

## Common Non-Discoverable Fields

- Assigned to

- Owned by

- Support group

- Change group

- Managed by group

- Location

- Accurate group data is critical for:

- o Proper incident routing

- o Efficient change execution

- o Operational accountability

Key takeaway: Discovery populates technical CI data; CMDB admins must enrich CIs with non-discoverable ownership and group information.

## 2. Service Mapping (Top-Down / ML-Powered, Tag-based discovery)

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

- o Operational CI used in ITSM/ITOM practices.

- o Can be environment-specific (Dev, Test, QA, Prod) or region-specific (AMS, EMEA, APJ).

- o Stored in cmdb_ci_service_auto or sub-classes.

- Service Map: Shows which CIs support a service, including applications, servers, middleware, and networks.

- o Helps identify service impact when components fail.

## Types of Application Services

## 1. Top-Down Mapping

- Pattern-Based:

- o Best for: Mission-critical apps.

- o Level: Surgical/Process-to-process.

- o Key: Most Granular.

- ML Connection Suggestions:

- o Best for: Homegrown & custom COTS.

- o Level: Traffic-based/Fingerprinting.

- o Key: Fastest Time-to-Value.

- Note: These two can be used together or individually.

## 2. Tag-Based Mapping

- Best for: Cloud-native, Containers, and VMs.

- Effort: Medium touch (requires defining tag categories/families).

- Key: Visualizes resource stacks across cloud infrastructure.

## 3. Dynamic CI Group

- Best for: Small application services.

- Mechanism: Uses CI list filters or CMDB queries.

- Effort: High touch (requires manual query building).


- Key: No License Required.

## Integration with CSDM:

- Supports Common Service Data Model (CSDM) by automating service and dependency modeling.

- Benefits include:

- o Accurate service modeling

- o Enhanced CMDB data quality

- o Dependency management for impact analysis and operational support

## Benefits:

- Enhanced visibility of IT services and dependencies

- Faster root-cause analysis for incidents and problems

- Proactive, low-risk change management

- Improved compliance and governance through clear documentation

Key takeaway: Service Mapping automates discovery and mapping of services and their dependencies, enabling IT teams to make informed decisions, reduce downtime, and improve service quality aligned with business objectives.

## 3. Agent Client Collector (ACC – Agent-Based)

- Requires installing an agent on each host.

- Provides real-time endpoint visibility.

- Collects hardware, software inventory, configuration details, and software usage data (key for SAM).

- Configuration Details: Captures system configuration details, including OS settings, patch levels, and network configurations.

- License: Paid.

- Note: Agent deployment is mandatory.

## Choose Agent Client Collector (ACC) when the scenario mentions:

- Laptops / workstations that are not always connected to the corporate network

- Remote users, VPN-based access, or devices that connect intermittently

- Security restrictions where the security team does not allow inbound scans or remote connections


- Highly secured / isolated networks (DMZ, restricted zones)

- Requirement to collect OS, software, processes, or security data directly from the endpoint

- Need for a single lightweight agent instead of multiple tools

## 4. IntegrationHub ETL

- Automates extract, transform, and load processes into CMDB and other tables.

- Supports data normalization and scheduled automation.

- License: No (available via ServiceNow Store).

- Note: Requires good understanding of ServiceNow and source data models.

## Non-CMDB Table Support for IntegrationHub ETL

IH-ETL includes advanced functionality that allows data ingestion into non-CMDB tables.

A list of non-CMDB tables supported by default are specified in the system property glide.identification_engine.non_cmdb_tables. These are the only tables that IH-ETL and IRE can work with. In addition, identification rules, including CI identifiers and identifier entries, must be created for these tables.

The following non-CMDB tables are supported in the latest release.

- Location [cmn_location]

- Department [cmn_department]

- Cost Center [cmn_cost_center]

- Building [cmn_building]

- User [sys_user]

- Group [sys_user_group]

The Discovery and Service Mapping Patterns application is a ServiceNow Store app.

New discovery patterns are released regularly through the ServiceNow Store, independent of major platform releases. This enables Discovery and Service Mapping customers to receive new or updated patterns without waiting for a full ServiceNow upgrade.

## 5. Service Graph Connectors

- Pre-built integrations to sync data from external systems (e.g., Azure, InTune, MS SCCM, Jamf, AWS)

- Ensures CMDB data consistency across tools.

- Can automatically synchronize and update the CMDB in real-time or


on a scheduled basis, reducing manual data entry and improving efficiency.

- License: Paid (except SCCM connector, which is free).

Note: Requires credentials for target systems.

## 6. Import Sets & Transform Maps (Legacy Method)

- Imports data from files, databases, or APIs into staging tables.

- Supports field mapping and transform scripts.

- License: No.

- Note: Does not use IRE by default, risking duplicates-recommended to enforce IRE via transform scripts.

## Utilizing IRE during a CMDB Import:

- The Identification and Reconciliation Engine (IRE) centrally identifies and reconciles CI data from multiple sources, including manual imports.

- Identification rules are defined per CI class and consist of identifier entries (unique attribute sets with priorities) and related entries.

- By default, IRE is not used during imports. It must be explicitly enabled using a custom onBefore script in the transform map.

- The CMDBTransformUtil API sends import set data to the IRE for identification before insert/update.

- IRE determines whether a CI is new or existing:

- o New CI → Insert into CMDB

- o Existing CI → Update the existing record

- When using CMDBTransformUtil, coalesce settings are ignored and are not required.

## Data Manager

Data Manager enables periodic certification and auditing of CMDB data to ensure accuracy and completeness.

- It uses scheduled certification policies that assign verification tasks to responsible users or groups.

## Two Methods to Auto-Populate Group Fields:

- CI Class Manager (Priority 2): Set Managed By Group at the CI class level; applies to all CIs in the class not linked to a Technology Management Offering.


- Technology Management Offering (Priority 1): Set Managed By, Support, and Change Groups at the offering level; applies to associated CIs and overrides CI Class Manager values.

Technology Management Offerings use dynamic CI groups behind the scenes to apply group values to their CIs.

CI Clos Manager: belonging by Group fo = Server hat Tem “Grange Managed Group by Group = CAB = Unix Support

- © Managed Group by Group = GAS = Cronge

- Group oy Group + server Taam

- Cronge oy Group + = Approve Group

- Managed by Group = ri

CI Attribute Population Using Technology Management Offering

- 1. Create a CMDB Group

- 2. Create a Dynamic CI Group

- 3. Create a Technology Management Service

- 4. Create a Technology Management Offering

- 5. Associate Dynamic CI Group to the Offering


## 6. Automatic Group Synchronization

- o System Business Rule (CSDM – Sync Group Attributes) syncs group values:

Service Builder is an alternative UI to achieve the same result, but it needs to be installed first from the ServiceNow store application.

When a Clis added to fhe CMDB hough ServiceNow Discovery or Asset Management, which of the following statements is true regarding the record's Discovery Source field? [Choose two)

- [1 field of ServiceNow. by SeniceN Clsdiscovered a discovery sour

- Cls discovered by ServiceN field of Service Mapping. y have a discovery sour

- Cis added othe CMDB through he Asset Management process have a discovery source field of

- [x] Cis added tothe CMDB through the Asset Management process have a discovery source field of Assethanagement

SNAssetManagement.

## Management Tools Overview

CMDB Workspace

## CMDB Governance

## 1. CMDB Health Dashboard

Monitors overall CMDB data quality through scorecards for Completeness, Correctness, and Compliance. It highlights top CI classes impacting health and allows drill-down analysis. Scheduled jobs must be manually activated for scorecards to populate.


## CMDB Health Dashboard:

Purpose: Provides a quick view of the overall quality of CMDB data using three key scorecards.

## 1. Completeness

- Measures whether CIs have all required and recommended fields populated, including non-discoverable data (e.g., ownership, support group).

Exam Tip: Missing essential data lowers completeness. Uses Recommended and Required metrics ServiceNow does not provide predefined required or recommended CI attributes in the CMDB. These must be defined by the CMDB administrator and relevant

stakeholders based on process requirements.

To prevent integrations (including Discovery and IRE) from failing due to missing mandatory CMDB attributes, ServiceNow provides two ways to override the default behavior:

- 1. Via CMDB Properties UI

- o Navigate to Configuration > CMDB Properties > Identification/Reconciliation Properties

- o Find “Enforce the requirement that required attributes cannot be null during identification and reconciliation”

- o Deselect the checkbox (set to false) and save.

- 2. Via System Properties (sys_properties.list)

- o Locate the property glide.required.attribute.enabled

- o Set its value to false.

## 👉 Exam takeaway:

Both methods disable enforcement of required attributes during IRE identification and reconciliation, allowing integrations to proceed even when mandatory fields are missing.

## 2. Compliance


- Shows how well CIs adhere to defined standards and audit policies. Uses Audit metric

- Exam Tip: Evaluates alignment with desired state configurations.

Compliance audits verify that CIs meet defined standards or policies. Typical examples include ensuring antivirus is installed, systems are patched to required levels, and mandatory ownership fields (such as Support Group and Managed by Group) are populated.

A common use case is system upgrades, where compliance audits identify servers that do not meet minimum hardware requirements (disk space, RAM, CPU) needed for the next upgrade. The Compliance Scorecard highlights non-compliant CIs so issues can be addressed before the upgrade.

## What Compliance Is Based On

- Audits comparing actual CI values vs expected values

- Expected values are defined via:

- o Certification Templates

- o Scripted Audits

## Common Audit Examples

- Antivirus installed on all workstations

- Linux servers on latest patch

- Production servers have Support Group and Managed by Group

- Hardware readiness for OS upgrades (RAM, disk, CPU)

- Key Rule (Very Important for Exam W)

## Scorecard: Only these audit types appear in the CMDB Health Dashboard Compliance

- Desired State audits

- Scripted audits

## 🚫 NOT included in the scorecard:

- Compliance

- Compliance Architecture

Compliance Scorecard Configuration (4 Required Components)


## 1️⃣ Certification Filter

- Defines scope of the audit (which CIs)

- Based on CI class and conditions

- Examples:

- o All Windows Computers

- o All UNIX servers in a datacenter

- Navigation:

- o CI Class Manager → Health → Compliance

- o OR Compliance > Filters

- 2ã Certification Template

- Defines conditions to pass the audit

- Can check:

- o Attributes

- o Relationships

- o Reference fields

- Must reference a Certification Filter

- Audit type must be = Desired State

- Example:

- o Windows Computers with RAM > 1000 MB

- Navigation:

- o CI Class Manager → Health → Compliance

- o OR Compliance > Templates

- 3ã Audit

- Executes the comparison:

- o Filtered CIs vs Template conditions

- Can:

- o Be scheduled

- o Create remediation tasks and assign It to a user or a group to work on It.

- Uses standard ServiceNow scheduler

- Navigation:

- o CI Class Manager → Health → Compliance


- o OR Compliance > Audits

- 4ã Compliance Score Calculation Job

- Calculates Compliance KPI after audits run

- Scheduled Job:

- o CMDB Health Dashboard – Compliance Score Calculation

- Navigation:

- o Configuration > Health Preferences > Scheduled Jobs

- Must be:

- o Activated

- o Run by a user with admin role

- Status table:

- o cmdb_health_metric_status

⚠️ If run by non-admin → inaccurate results

- Scripted Audits

- Used when templates are too restrictive

- Logic defined in script

- Still use:

- o Certification Filter

- Included in Compliance Scorecard

- Cannot be created via CI Class Manager

- Navigation:

- o Compliance > Desired State > Scripted Audits > Audits

- Base system includes sample:

- o Data Center Zone Usage

## Desired State vs Data Manager (Exam Favorite 💡)

- CMDB Health Desired State Audits

- Automatic

- Ensures fields are:

- o Present

- o Configured correctly


- Example:

- o Server has an owner and support group

## Data Manager Certification Policies

- Manual verification

- Used when data:

- o Cannot be discovered automatically

- Generates certification tasks/checklists

- Example:

- o Confirm Joe Smith is the correct owner of ServerXYZ

## 👉 They serve different purposes and are NOT the same

Which of the following are used when configuring a Desired State audit? Select all that apply.

Certification Templates

- Certification Fiters

- Audit

[x] Recommended Fields

Duplicates

[x] Policies

## 3. Correctness

- Checks accuracy of CMDB data, including duplicates, outdated CIs, and proper relationships. Uses Duplicate, Orphan, and Staleness metrics

- Exam Tip: A CI passes correctness only if it meets all defined metrics.

## Score Calculation


- Overall percentage = % of CIs that pass all metrics, not an average of individual metrics.

- Example: Metrics: 93%, 100%, 96%  overall = 89% (because only 89% of CIs met all metrics).

## 1. Duplicate CIs

## Definition

- Occurs when multiple CMDB records exist for a single real-world CI.

## Key Points

- Evaluated using predefined identification rules.

- Only independent CIs are evaluated (e.g., hardware, servers - not applications).

- Duplicates can be detected via:

- o ServiceNow Discovery

- o CMDB Correctness job

## Behavior

- A de-duplication task is automatically created.

- The oldest CI record (based on sys_created_on) is treated as the primary (non- duplicate).

- Newer records are marked as duplicates via the Duplicate Of field.

## Insights Provided

- Classes with the highest number of duplicates

- Discovery sources or CI owners causing duplication (root cause analysis)

## 2. Orphan CIs

## Definition

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

## 3. Stale CIs

## Definition

- CIs not updated within a defined time period.

## Base Rule

- Default staleness rule:

- o Class: cmdb_ci

- o Threshold: 60 days

- o Applies to all child classes unless overridden

## How Updates Are Determined

- Based on sys_updated_on

- Even if no attribute changes occur, a discovery scan updates this field

## Custom Rules (Best Practice)

- Different CI classes can have different staleness thresholds:

- o Network devices scanned every 14 days → staleness = 21 days

- o Servers discovered daily → staleness = 7 days

## Why It Matters

- Prevents use of non-existent or outdated CIs

- Critical for lifecycle management and downstream processes

## Configuration & Governance

- CI Class Manager

- Used to configure Correctness Scorecard rules

- Supports:

- o Duplicate identification

- o Orphan rules

- o Staleness rules by class

## Exam Takeaways (High-Probability Questions)

Correctness Scorecard measures Duplicate, Orphan, and Stale CIs


- Duplicate metric applies only to independent CIs

- Oldest CI = primary, newer ones = duplicates

- No default orphan rules → must be configured manually

- Base staleness rule = 60 days at cmdb_ci

- sys_updated_on drives staleness calculation

- Metrics roll up into the CMDB Health Dashboard

## Manage & Remediate Duplicate CIs — Exam Notes

- What Are Duplicate CIs?

- Duplicate CIs = two or more CMDB records representing the same real-world item.

- They negatively impact:

- o Incident, Change, and Problem Management

- o Reporting & compliance

- o Trust in CMDB data

## Common Causes of Duplicate CIs

## Know these for scenario-based questions:

- Discovery tools (multiple tools discovering the same CI differently)

- Import Sets without proper identification rules

- Third-party integrations (REST/SOAP) without IRE logic

- Manual CI creation (poor governance, no naming standards)

- Incorrect or missing Identification Rules

- Lack of CMDB governance

## How ServiceNow Determines Duplicates

- Duplicates are detected by the Identification and Reconciliation Engine (IRE).

- IRE uses:

- o Identification Rules → determine what uniquely identifies a CI

- o Reconciliation Rules → determine which data source wins

- If multiple CIs match identification rules:

- o A de-duplication task is created

- o Visible in CMDB Workspace


## ⚠️ Important Exam Gotcha

- If duplicate CIs already have a Discovery Source populated, the CMDB Health Dashboard Correctness Scorecard will NOT flag them

- Once rediscovered and reprocessed by IRE  they will be flagged and a de- duplication task is generated

Duplicate CIs are only flagged by CMDB Health after they are processed by IRE — existing duplicates with a populated Discovery Source are ignored until rediscovery happens.

## Discovery Behavior with Duplicates

- When duplicates are found during Discovery:

- o Oldest CI (by creation date) is updated

- o Others are marked as duplicates

## Key Field Change (Important Update 🚨)

- Old: Discovery Source field was used to indicate duplicates

- New: Duplicate of field

- Reason:

- o Preserve the Discovery Source with the last discovery tool

- Functionality remains the same

## De-duplication Tasks

- Created automatically when IRE detects duplicates

- Allow admins to:

- o Review duplicate CIs

- o Decide how to remediate them

## Access:

- Legacy: De-duplication Tasks module

## Current: CMDB Workspace

## Duplicate CI Remediator

- Wizard launched from a de-duplication task

- Admin can:


- o Select Main CI

- o Merge attributes

- o Maintain audit trail

- Supports:

- o Merge

- o Retain one CI

- o Eliminate duplicates

## De-duplication Templates

## Used for bulk remediation:

- Pre-configured remediation logic

- Applied:

- o Per CI class

- o In bulk

- Managed from:

- o De-duplication Dashboard in CMDB Workspace

- Templates can be:

- o Organized into libraries

- o Executed on multiple de-duplication tasks at once

## System Properties for Duplicate Handling


## Property

glide.identification_engine.skip_duplicates

glide.identification_engine.skip_duplicates.threshold Max duplicates allowed (default: 5)

## Purpose

Skips duplicates (default: true)

## Behavior:

- If duplicates < threshold:

- o Oldest CI is updated

- o Others get Duplicate of populated

- IRE ignores CIs where Duplicate of is populated

## Now Assist for CMDB (AI-based)

Know what it does, not how to configure:

- Uses Generative AI

- Automates:

- o Duplicate CI detection

- o CI summarization

- o Suggested remediation steps

- Works with:

- o De-duplication templates

- o CMDB Workspace

- Goal:

- o Reduce manual effort

- o Improve CMDB accuracy & governance

## Why Handling Duplicates Matters (Exam Framing)

- Ensures CMDB as a Single Source of Truth

- Improves:

- o IT operations

- o Reporting & compliance

- o Decision-making

## One-Line Exam Summary


Duplicate CIs are identified by the IRE using identification rules, managed via de- duplication tasks in CMDB Workspace, remediated using the Duplicate CI Remediator or de-duplication templates, and flagged using the Duplicate of field—not Discovery Source.

Cloud Dimensions is reviewing the metrics provided by thelr CMDB Correctness Scorecard.

In reviewing the Duplicate metric for the Server class, it displays Healthy Cls/Evaluated 700/800.

Which of the following is frue regarding the duplicate server records calculated on the Duplicate metric?

- (¥) records are duplicates in the CMDB

- 800 server records are duplicates in the CMDB.

- 100 server records are duplicates in the CMDB

- (3) 700 Linux and 800 Windows server records are duplicates in the CMDB.

the number of

Thersfore 100 are duplicate records.
