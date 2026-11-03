# ServiceNow CMDB & CSDM Reference Guide

> **Extraction notes (remove before ingesting, or keep as a data-quality log):**
> This file was restructured from a `marker`-generated markdown export. Changes made: added heading hierarchy, normalized all bullets to `-`, rebuilt two comparison tables that had collapsed into run-on paragraphs (likely a two-column PDF layout), separated a block where "Discovery Source Field" and "Non-Discoverable Data" had merged into one paragraph, and fixed duplicated list numbers (e.g. source had "2 2 Service", "3 3 Service Offering"). Two spots are flagged inline with `[VERIFY]` because the correction is a guess — check them against the source PDF. No content was added or removed, only reformatted.

## CMDB vs. CSDM (Overview)

The CMDB is the database, while the Common Service Data Model (CSDM) is the data model. The data model helps determine where to record items in the CMDB, and what relationships are important to drive business value.

## Key Terms & Definitions

- **Configuration Item (CI):** Physical and logical components of an infrastructure that need to be managed to deliver a product or service, and are currently, or soon will be, under configuration management. Examples: a network device, a server, an application, a delivery truck, or a service.
- **Attribute:** Information that further describes a CI, such as a name, serial number, manufacturer, or operating system.
- **Relationship Type:** The relationships between configuration items — for example, a web application might read data from a specific database, which in turn might depend on a piece of underlying hardware.
- **Class:** A table that contains and represents a specific type or group of CIs that share common attributes, such as a Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, or Animal.
- **Configuration Management Database (CMDB):** A database used to store configuration records throughout their lifecycle. The Configuration Management System maintains one or more CMDBs, and each CMDB stores attributes of CIs and relationships with other CIs.
- **Base Table:** The core Configuration Item (`cmdb_ci`) table, which stores the basic attributes of all CIs. All configuration item classes extend from this table, including all hardware and applications.
- **CI Reclassification:** A CI whose class has been upgraded, downgraded, or switched. Example: a Server record upgraded from the Server (`cmdb_ci_server`) class to the Windows Server (`cmdb_ci_win_server`) class.
- **Parent and Child Class:** A table that extends another table is a *child class*; the table it extends is the *parent class*. A table can be both parent and child, extending one table while being extended by another. Example: the Server table extends the Computer table, and the Windows Server table extends the Server table — making the Server table both a parent and a child class.

## Asset vs. Configuration Item (CI)

On the Now Platform, creating a hardware asset automatically creates a corresponding CI, and discovering a CI for the first time automatically creates a corresponding asset record. The asset and the CI stay connected throughout the CI/asset lifecycle.

| | Asset | Configuration Item (CI) |
|---|---|---|
| **Typically starts** | During procurement, but may be created when a discovery tool first finds it | When a discovery tool first finds it, but may be created during procurement |
| **Belongs to** | The financial lifecycle | Technical operations |

## Common Services Data Model (CSDM) — Related Terms

- **CSDM:** Represents a standard and shared set of service-related definitions across ServiceNow products and the Now Platform. It enables and supports true service-level reporting while providing prescriptive guidance on service modeling within the CMDB. These definitions span the ServiceNow product portfolio and the Now Platform.
- **Application Service:** A set of interconnected applications and hosts configured to offer a service to the organization. Can be internal (e.g. an organization's email system) or customer-facing (e.g. an organization's website).
- **Application:** The applications that comprise an application service, stored as CIs in the CMDB along with the relationships between them (e.g. Tomcat, Apache, Microsoft SQL, Oracle, IIS).
- **DevOps:** The combination of developers (who build applications) and operations groups (who deploy and maintain them) into one team, to work more effectively together and accelerate/improve service delivery.
- **Principal Class:** Can be configured to limit which CI classes display in the Configuration Item fields on incident, problem, and change records.
- **Logical CI:** Does not take up physical space; performs specific functions that require physical components to operate. Examples include Service Offering, Service, and Business Application — all manually entered into the CMDB.

## Stakeholder Roles in CMDB Implementation

Each stakeholder has different goals and outcomes they want from a CMDB implementation:

- Import CI data, such as name, source, and relationships
- Determine specific CI information required to support capabilities and build organizational buy-in
- Create a go-forward strategy for configuration management responsibilities
- Identify necessary reports showing CI health for related departments

## Worked Examples: Logical CI → Physical CI Dependencies

**1. Business Application** `[VERIFY: source read "1 IB Business Application" — "IB" may be an OCR artifact for "IT"]`
- Logical CI: Microsoft Teams (the collaboration/chat app used by employees)
- Physical CIs it depends on:
  - Cloud servers hosting Teams
  - Network infrastructure (routers, switches)
  - Databases storing user info and messages

**2. Service**
- Logical CI: Corporate Email Service
- Physical CIs it depends on:
  - Exchange Server or Office 365 backend
  - Mail servers
  - Storage for email data
  - Network connections for email delivery

**3. Service Offering**
- Logical CI: VPN Access for Remote Employees
- Physical CIs it depends on:
  - VPN servers
  - Firewalls
  - Network links to the corporate office

**4. Other Examples**
- Logical CI: HR Payroll System — depends on payroll application servers, database servers, authentication servers
- Logical CI: Customer-Facing Website — depends on web servers, application servers, load balancers, content delivery network

> **Tip:** Logical CI = what the business sees / uses. Physical CI = what actually runs it behind the scenes.

## Foundation Data

Not part of the CMDB, but referenced in CI records.

## CMDB Design Considerations

Selecting the appropriate CI classes, levels, attributes, and relationships is one of the most important and challenging aspects of CMDB design. During a CMDB health check, ServiceNow examines the number of custom classes and attributes created, and assesses whether these custom attributes are established at the correct level.

ServiceNow provides a free store application called **CMDB CI Class Models** that can be installed on a ServiceNow instance to obtain a wide range of additional classes not provided in a base instance.

**Automated discovery tools by ServiceNow:**
- ServiceNow Discovery
- Service Mapping
- Agent Client Collector

## Configuration & Asset Management Lifecycles

An asset becomes a CI (Configuration Item) when it is deployed, and remains a CI throughout its lifecycle until it is returned to stock or disposed of. Configuration Management and IT Asset Management are distinct, yet complementary, practices.

*(Note: the source document referenced an accompanying diagram here that was not captured by the extraction. Re-run image extraction or consult the original PDF for the visual.)*

## Change Control Board (CCB)

The CCB is a team of people that ensures your CMDB delivers continuous value. This team sets direction and makes decisions on what is needed to ensure the CMDB can support the organization's strategic initiatives, and determines whether the CMDB is ready for utilization.

## The Three Pillars of CMDB Health

To operationalize and maintain the health of the CMDB, ServiceNow defines three pillars of success. Each pillar focuses on a key customer pain point:

1. **Ingestion of CMDB data** — how the CMDB is populated and the data is identified and reconciled. Automate as much of the data flow into the CMDB as possible, at a frequency that supports your stated use cases.
2. **Governance of the data** — getting data in is just the beginning; next is management and upkeep of the data to maintain a healthy CMDB and gain value from it.
3. **Insight into the data** — how you visualize and utilize this data across the platform.

## ServiceNow CMDB Data Population & Discovery Methods (Ingestion)

ServiceNow provides multiple approaches to populate and maintain the CMDB, ranging from automated discovery to integrations and data imports. Each method serves a specific purpose and has its own licensing and configuration considerations.

### 1. ServiceNow Discovery (Horizontal / Agentless, IP-Based)

- Automatically discovers infrastructure (servers, network devices, applications)
- Populates the CMDB and maps dependencies between components
- **License:** Paid (ITOM Visibility)
- Discovered data should be enriched with non-discoverable attributes (e.g. support group, managed by)
- Schedule-based; not real-time
- Uses probes and sensors to determine device type

#### MID Server

The MID Server (Management, Instrumentation, and Discovery Server) is deployed inside the organization's trusted network.

- Acts as a secure bridge between the ServiceNow instance and internal systems not directly accessible due to firewalls or network restrictions
- All communication between ServiceNow and the MID Server is encrypted
- ServiceNow sends probes to the MID Server; the MID Server executes them and returns results, which sensors use to update the CMDB
- Discovery is agentless and uses standard protocols:
  - WMI for Windows
  - SSH for Linux/Unix
  - SNMP for network devices
- Ensures secure, scalable Discovery without exposing internal systems to the internet

> **Key takeaway:** ServiceNow never directly connects to internal devices — everything goes through the MID Server.

#### Discovery Schedules

Discovery Schedules define when, what, and where Discovery runs. Used for horizontal Discovery (network-based scanning). Specify:

- IP ranges / scope
- Schedule timing
- Assigned MID Server(s)

Can target on-prem environments or cloud service accounts. Schedules trigger Discovery using probes, sensors, and patterns to identify and update CIs in the CMDB.

#### Discovery Admin Workspace (Schedules Page)

Central hub to monitor and manage Discovery operations, with real-time visibility into Discovery activity and performance. Key reports include:

- Schedules by location (map)
- Total schedules (last 24 hours)
- Errors by category
- Total Discovery attempts (completed vs. canceled)

> **Key takeaway:** Discovery Schedules control horizontal Discovery execution and are monitored through the Discovery Admin Workspace.

#### Types of Discovery

- **Network Discovery** — identifies internal IP address ranges; not required if IP ranges are already known
- **CI Discovery** — discovers devices, servers, and applications; the most commonly used Discovery type
- **Cloud Discovery** — discovers AWS and Azure resources using cloud credentials and APIs
- **Serverless Discovery** — discovers applications without discovering the host first; pattern-based, not reliant on traditional host discovery

> **Key takeaway:** All are forms of horizontal Discovery, each targeting different environments and use cases.

#### Limiting Discovery Data

Benefits of limiting Discovery scope:

- **Improves data accuracy** — avoids populating the CMDB with low-priority/irrelevant data; establishes a strong foundation with high-quality CIs
- **Prevents CMDB data overload** — reduces clutter from unnecessary Discovery results; keeps the CMDB clean and maintainable
- **Faster initial deployment** — fewer devices scanned means quicker Discovery cycles, enabling a usable CMDB early with gradual expansion later
- **Simplifies CMDB management** — focuses on key CI classes (e.g. servers, critical applications); keeps data immediately relevant to business needs
- **Better stakeholder buy-in** — quick wins with accurate data build trust and encourage support for broader Discovery adoption

> **Key takeaway:** Start small, discover what matters first, then expand Discovery incrementally.

#### Discovery Ranges

Discovery ranges define which IP addresses ServiceNow Discovery scans. You can include or exclude specific IP ranges in a Discovery schedule.

| Range type | Example | Characteristics |
|---|---|---|
| **Broad Ranges (Subnets)** | `192.168.0.0/24`, `10.11.128.192/26` | Includes network and broadcast addresses; scans a large number of IPs, which may cause data overload, redundant/irrelevant CIs, and Discovery errors. Not recommended during initial implementation. Best practice: don't exceed `/16` (~65,000 IPs) — split into smaller ranges if needed. |
| **Limited Ranges (preferred initially)** | `192.168.0.1–192.168.0.254`, `10.11.128.193–10.11.128.254` | Excludes network and broadcast addresses; targets specific, known devices. Improves data quality, performance, and troubleshooting; supports clean, manageable CMDB growth. |

> **Key takeaway:** Start with small, targeted IP ranges and expand Discovery gradually to avoid CMDB data overload.

#### Discovery Configuration Console

- Used to control what Discovery detects (devices, applications, software, and CIs)
- Allows including or excluding specific CI types from Discovery
- Excluding a CI disables the related probe or classifier
- Helps CMDB teams focus on principal CI classes only, reducing noise and clutter
- Access path: **Discovery Definition → Configuration Console**

> **Key takeaway:** Use the Configuration Console to limit Discovery to only the CIs you want to manage.

#### Discoverable vs. Non-Discoverable Data

**Discoverable data** — hardware, software, and network information collected by ServiceNow Discovery on a scheduled basis:

| Category | Examples |
|---|---|
| Hardware | CPU, memory, storage |
| Software | Operating systems, installed applications |
| Network | IP address, MAC address, topology |
| Cloud resources | AWS, Azure, Google Cloud |

**Non-discoverable data** — cannot be collected by automated tools like Discovery, Service Mapping, or Service Graph Connectors. Must be manually maintained or populated via automation after Discovery. Used to support ITSM processes such as Incident, Change, and Problem Management. Common non-discoverable fields:

- Assigned to
- Owned by
- Support group
- Change group
- Managed by group
- Location

Accurate group data is critical for proper incident routing, efficient change execution, and operational accountability.

> **Key takeaway:** Discovery populates technical CI data; CMDB admins must enrich CIs with non-discoverable ownership and group information.

#### Discovery Source Field

- Newly discovered CIs are created with Discovery source = **ServiceNow**
- If a CI already exists (e.g. created via Asset Management), the source may initially be **SNAssetManagement**
- Once discovered, the Discovery source is updated to **ServiceNow**
- The Discovery source always reflects the last authoritative discovery method

### 2. Service Mapping (Top-Down / ML-Powered, Tag-Based Discovery)

- Builds end-to-end service maps showing how business services are supported by IT components
- Dynamically updates relationships as changes occur
- **License:** Paid (ITOM Visibility)
- Follow CSDM guidelines, define service owners, and relate services to business applications

#### Business Value

- Bridges the gap between IT Operations and business users
- Aligns IT service delivery with business outcomes, not just infrastructure
- Supports ITSM processes: Incident, Problem, and Change Management

#### Key Concepts

- **Application Service:** Logical representation of a deployed system, application, or product stack. An operational CI used in ITSM/ITOM practices. Can be environment-specific (Dev, Test, QA, Prod) or region-specific (AMS, EMEA, APJ). Stored in `cmdb_ci_service_auto` or its sub-classes.
- **Service Map:** Shows which CIs support a service, including applications, servers, middleware, and networks. Helps identify service impact when components fail.

#### Types of Application Services

1. **Top-Down Mapping**
   - **Pattern-Based:** best for mission-critical apps; surgical/process-to-process level; most granular
   - **ML Connection Suggestions:** best for homegrown & custom COTS apps; traffic-based/fingerprinting level; fastest time-to-value
   - *(Note: these two can be used together or individually.)*
2. **Tag-Based Mapping** — best for cloud-native, containers, and VMs; medium-touch effort (requires defining tag categories/families); visualizes resource stacks across cloud infrastructure
3. **Dynamic CI Group** — best for small application services; uses CI list filters or CMDB queries; high-touch effort (requires manual query building)