

The CMDB is the database while the Common Service Data Model (CSDM) is the data model. The data model helps determine where to record items in the CMDB, and what relationships are important to drive business value.

## Configuration Item (CI)

Physical and logical components of an infrastructure that needs to be managed to deliver a product or service and are currently, or soon will be, under configuration management. For example, a network device, a server, an application, a **delivery truck**, or service.

### Attribute

Information that further describes a CI such as a name, serial number, manufacturer, operating system.

### Relationship Type

Include the relationships between configuration items. For example, a web application might read data from a specific database, which in turn might depend on a piece of underlying hardware.

### Class

Describes a table that contains and represents a specific type or group of CIs that share common attributes such as a Windows Server, Linux Server, Printer, Virtual Machine, **Vehicle, Animal** etc.

### Configuration Management Database (CMDB)

A database used to store configuration records throughout their Lifecycle. **The Configuration Management System maintains one or more CMDBs**, and each CMDB stores attributes of CIs, and Relationships with other CIs.

### Base Table

The core Configuration Item [**cmdb\_ci**] table, which stores the basic attributes of all the CIs. **All configuration item classes extend from this table** including all hardware and applications.

### CI Reclassification

Is a CI whose **class** has been **upgraded, downgraded, or switched**. An example of an upgraded CI is a Server record that was upgraded from the Server [cmdb\_ci\_server] class to the Windows Server [cmdb\_ci\_win\_server] class.

### Parent and Child Class

A table that extends another table is called a child class, and the table it extends is the parent class. A table can be both a parent and child class both extending and providing extensions for other tables. For example, the Server table extends the Computer table and the Windows Server table extends the Server table, thus making the Server table both a Parent and Child class.

### Asset vs. CI

On the Now platform, when creating a hardware asset, a corresponding CI will be automatically created or when a CI is discovered for the first time and inserted into the CMDB, a corresponding asset record will be automatically created. The asset and the CI is connected through out the CI/Asset lifecycle.

#### Asset:

- Often starts during the procurement process, but may be created when a discovery tool finds the CI for the first time
- Is part of the financial lifecycle

### Configuration Item (CI):

- Often starts when a discovery tool finds the CI for the first time, but may be created during the procurement process
- Is part of the technical operations

### Common Services Data Model (CSDM)

Represents a standard and shared set of **service related definitions** across ServiceNow products and the NOW platform that enables and supports true service level reporting while providing prescriptive guidance on service modeling within the CMDB. These service-related definitions span the ServiceNow® product portfolio and the Now Platform®.

### Application Service

**A set of interconnected applications and hosts** which are configured to **offer a service to the organization**. Application services can be internal, like an organization email system

or customer-facing, like an organization website.

### Application

Applications that comprise an application service as configuration items (CIs). The various Applications and the relationships between them, that comprise an application service, are stored in the CMDB. (i.e. Tomcat, Apache, Microsoft SQL, Oracle, IIS).

### DevOps

Consists of developers who build applications and the operations groups who deploy and maintain them within an enterprise. In a DevOps environment, these two groups are combined into one in order to work more effectively together to accelerate and improve service delivery.

### Principal Class

Principle Classes can be configured **to limit the CI classes that display** in the Configuration Item fields on incident, problem, and change records.

### Logical CI

Do not take up space. They perform specific functions requiring physical components in order to operate. Examples include Service Offering, Service, Business Application which are manually entered into the CMDB.

Each stakeholder will have different goals and outcomes they want to realize from a CMDB implementation. What is the stakeholder's role in implementing and maintaining the CMDB?

- ☐ Import CI data, such as name, source, and relationships
- ☒ Determine specific CI information required to support capabilities and build organizational buy-in
- ☐ Create a go-forward strategy for configuration management responsibilities
- ☐ Identify necessary reports showing CI health for related departments

![A green checkmark icon inside a circle, indicating a correct answer.](f5fd8a6b12eff431b5d2cc73cad225b0_img.jpg)

A green checkmark icon inside a circle, indicating a correct answer.

Correct

You will need to involve the right stakeholders to determine the specific CI information required to support these capabilities and build organizational buy-in. This stakeholder group should include the process owner, process manager, and other subject matter experts for each of the processes.

Examples:

### 1 Business Application

- **Logical CI:** "Microsoft Teams" (the collaboration/chat app used by employees)

- **Physical CIs it depends on:**
  - Cloud servers hosting Teams
  - Network infrastructure (routers, switches)
  - Databases storing user info and messages
- 

### 2 ~~2~~Service

- **Logical CI:** “Corporate Email Service”
- **Physical CIs it depends on:**
  - Exchange Server or Office 365 backend
  - Mail servers
  - Storage for email data
  - Network connections for email delivery
- 

### 3 ~~3~~Service Offering

- **Logical CI:** “VPN Access for Remote Employees”
- **Physical CIs it depends on:**
  - VPN servers
  - Firewalls
  - Network links to the corporate office
- 

### 4 ~~4~~Other Examples

- **Logical CI:** “HR Payroll System”
  - Depends on: Payroll application servers, database servers, authentication servers.
- **Logical CI:** “Customer-Facing Website”
  - Depends on: Web servers, application servers, load balancers, content delivery network.
- 

💡 **Tip:** A simple way to think of it:

**Logical CI = What the business sees / uses**

**Physical CI = What actually runs it behind the scenes**

Foundation data:

Not part of the CMDB, but referenced in the CI records.

![Diagram showing the hierarchy of organizational entities: Location (cmn_location) branching into Building (cmn_building), Cost Center (cmn_cost_center), and Company (cmn_company). Cost Center branches into Department (cmn_department). User (sys_user) is linked to Company, Department, and Group (sys_user_group). Group is linked to Group Member (sys_user_grmember). User is linked to Roles (sys_user_role). Group Member is linked to Group Roles (sys_user_group). Roles and Group Roles both point to a final Roles (sys_user_has_role) entity.](690fce4fb5c9cbb8beb560cb2a3fcbeb_img.jpg)

```
graph TD; Location[Location  
cmn_location] -- Parent --> Building[Building  
cmn_building]; Location --> CostCenter[Cost Center  
cmn_cost_center]; Location --> Company[Company  
cmn_company]; CostCenter -- Parent --> Department[Department  
cmn_department]; Company -- Parent --> User[User  
sys_user]; Department -- Parent --> User; Company --> Group[Group  
sys_user_group]; Group --> GroupMember[Group Member  
sys_user_grmember]; User --> Roles1[Roles  
sys_user_role]; GroupMember --> GroupRoles[Group Roles  
sys_user_group]; Roles1 --> Roles2[Roles  
sys_user_has_role]; GroupRoles --> Roles2;
```

Diagram showing the hierarchy of organizational entities: Location (cmn\_location) branching into Building (cmn\_building), Cost Center (cmn\_cost\_center), and Company (cmn\_company). Cost Center branches into Department (cmn\_department). User (sys\_user) is linked to Company, Department, and Group (sys\_user\_group). Group is linked to Group Member (sys\_user\_grmember). User is linked to Roles (sys\_user\_role). Group Member is linked to Group Roles (sys\_user\_group). Roles and Group Roles both point to a final Roles (sys\_user\_has\_role) entity.

![Diagram showing the relationship between CMDB classes and CI records. The central node is cmdb_ci. It is connected to sys_user, sys_user_group, core_company, cmn_cost_center, and cmn_location. sys_user is connected to Assign_to, Owned_by, Managed_by, and Supported_by. sys_user_group is connected to Assignment_group, Change_control, and Support_group. core_company is connected to Company, Manufacturer, and Vendor. cmn_cost_center is connected to Department. cmn_location is connected to Location. cmdb_ci is also connected to Model ID, Asset, and Maintenance Schedule. Model ID is connected to cmdb_model. Asset is connected to alm_asset. Maintenance Schedule is connected to cmn_schedule.](e394c2b5c61344f6a12397f430086072_img.jpg)

```
graph TD; cmdb_ci[cmdb_ci] -.-> sys_user[sys_user]; cmdb_ci -.-> sys_user_group[sys_user_group]; cmdb_ci -.-> core_company[core_company]; cmdb_ci -.-> cmn_cost_center[cmn_cost_center]; cmdb_ci -.-> cmn_location[cmn_location]; sys_user --> Assign_to[Assign_to]; sys_user --> Owned_by[Owned_by]; sys_user --> Managed_by[Managed_by]; sys_user --> Supported_by[Supported_by]; sys_user_group --> Assignment_group[Assignment_group]; sys_user_group --> Change_control[Change_control]; sys_user_group --> Support_group[Support_group]; core_company --> Company[Company]; core_company --> Manufacturer[Manufacturer]; core_company --> Vendor[Vendor]; cmn_cost_center --> Department[Department]; cmn_location --> Location[Location]; cmdb_ci -.-> Model_ID[Model ID]; cmdb_ci -.-> Asset[Asset]; cmdb_ci -.-> Maintenance_Schedule[Maintenance Schedule]; Model_ID --> cmdb_model[cmdb_model]; Asset --> alm_asset[alm_asset]; Maintenance_Schedule --> cmn_schedule[cmn_schedule];
```

Diagram showing the relationship between CMDB classes and CI records. The central node is cmdb\_ci. It is connected to sys\_user, sys\_user\_group, core\_company, cmn\_cost\_center, and cmn\_location. sys\_user is connected to Assign\_to, Owned\_by, Managed\_by, and Supported\_by. sys\_user\_group is connected to Assignment\_group, Change\_control, and Support\_group. core\_company is connected to Company, Manufacturer, and Vendor. cmn\_cost\_center is connected to Department. cmn\_location is connected to Location. cmdb\_ci is also connected to Model ID, Asset, and Maintenance Schedule. Model ID is connected to cmdb\_model. Asset is connected to alm\_asset. Maintenance Schedule is connected to cmn\_schedule.

One of the most important and challenging aspects of CMDB design is selecting the appropriate CI classes, levels, attributes, and relationships to be used as part of a CMDB implementation. **During a CMDB health check, ServiceNow examines the number of custom classes and attributes created and assesses whether these custom attributes are established at the correct level. ServiceNow provides a free store application called [CMDB CI Class Models](#) that can be installed on a ServiceNow instance to obtain a wide range of additional classes that are not provided in a base instance.**

**Automated discovery tools by SN:** ServiceNow Discovery, Service Mapping, or Agent Client Collector

## **Configuration and Asset Management Lifecycles**

An asset becomes a CI (Configuration Item) when it is deployed and remains a CI throughout its lifecycle until it is returned to stock or disposed of. As illustrated in the diagram, Configuration Management and IT Asset Management are distinct, yet complementary practices.

![A complex diagram showing the intersection of Configuration Management and Asset Management lifecycles. The top half, labeled 'Asset Management', follows a linear path: Requirement -> Request -> Approval -> Procure -> Receive -> Tagging -> Storage. The bottom half, labeled 'Configuration Management', follows a circular 'Operational Life-cycle': Upgrade -> Move -> Uninstall -> Dispose. A central 'Asset Life-cycle' overlapping both includes: Break/Fix, Configure, Billing, Redeploy, and CMDB. Arrows show the flow between these stages, indicating how an asset becomes a configuration item upon deployment and remains one until disposal or return to storage.](a7d78d22e465dea388b31d0739f9d0cd_img.jpg)

```
graph TD
    subgraph Asset_Management [Asset Management]
        R[Requirement] --> Re[Request] --> A[Approval] --> P[Procure] --> Rv[Receive] --> T[Tagging] --> S1[Storage]
    end
    subgraph Configuration_Management [Configuration Management]
        U[Upgrade] --> M[Move] --> U[Uninstall] --> D[Dispose]
    end
    subgraph Asset_Life_Cycle [Asset Life-cycle]
        BF[Break / Fix] --> C[Configure] --> B[Billing] --> Red[Redeploy] --> CMDB[CMDB]
    end
    R --> Re --> A --> P --> Rv --> T --> S1 --> Dep[Deploy] --> CMDB
    CMDB --> Red --> Dep --> CMDB
    CMDB --> BF --> C --> B --> Red --> CMDB
    CMDB --> U --> M --> U --> D
```

A complex diagram showing the intersection of Configuration Management and Asset Management lifecycles. The top half, labeled 'Asset Management', follows a linear path: Requirement -> Request -> Approval -> Procure -> Receive -> Tagging -> Storage. The bottom half, labeled 'Configuration Management', follows a circular 'Operational Life-cycle': Upgrade -> Move -> Uninstall -> Dispose. A central 'Asset Life-cycle' overlapping both includes: Break/Fix, Configure, Billing, Redeploy, and CMDB. Arrows show the flow between these stages, indicating how an asset becomes a configuration item upon deployment and remains one until disposal or return to storage.

![A flowchart depicting the lifecycle of an asset from Ideation to End of Life. Stages include: Ideation (Under Evaluation, Pilot), Purchase (On Order, Pre-Allocated), Design (Build), Inventory (Available, Pending Repair, Pre-Allocated, Reserved), Deploy (In Stock, In Transit, Pending Transfer, Reserved), Operational (In Use, In Maintenance), and End of Life (Disposed, Donated, In Transit, Pending Disposal, Sold, Vendor Credit, Obsolete - CI, RMA - CI). Sub-stages for Missing (Lost, Stolen) and Defective (In Stock, In Transit) are also shown. Management responsibilities like Strategic Portfolio Mgmt, Procurement, Asset Mgmt, and CMDB Mgmt are mapped to their respective stages.](88b0f3f4393228e9ea4d6542aef7c399_img.jpg)

```
graph LR
    subgraph Ideation
        I1[Under Evaluation]
        I2[Pilot]
    end
    subgraph Purchase
        P1[On Order]
        P2[Pre-Allocated]
    end
    subgraph Design
        D1[Build]
    end
    subgraph Inventory
        I3[Available]
        I4[Pending Repair]
        I5[Pre-Allocated]
        I6[Reserved]
    end
    subgraph Deploy
        D2[In Stock]
        D3[In Transit]
        D4[Pending Transfer]
        D5[Reserved]
    end
    subgraph Operational
        O1[In Use]
        O2[In Maintenance]
    end
    subgraph End_of_Life [End of Life]
        EL1[Disposed]
        EL2[Donated]
        EL3[In Transit]
        EL4[Pending Disposal]
        EL5[Sold]
        EL6[Vendor Credit]
        EL7[Obsolete - CI]
        EL8[RMA - CI]
    end
    subgraph Missing
        M1[Lost]
        M2[Stolen]
    end
    subgraph Defective
        Def1[In Stock]
        Def2[In Transit]
    end

    Ideation --> Purchase
    Purchase --> Design
    Design --> Inventory
    Inventory --> Deploy
    Deploy --> Operational
    Operational --> End_of_Life
    End_of_Life --> Missing
    End_of_Life --> Defective
    Missing --> End_of_Life
    Defective --> End_of_Life
```

A flowchart depicting the lifecycle of an asset from Ideation to End of Life. Stages include: Ideation (Under Evaluation, Pilot), Purchase (On Order, Pre-Allocated), Design (Build), Inventory (Available, Pending Repair, Pre-Allocated, Reserved), Deploy (In Stock, In Transit, Pending Transfer, Reserved), Operational (In Use, In Maintenance), and End of Life (Disposed, Donated, In Transit, Pending Disposal, Sold, Vendor Credit, Obsolete - CI, RMA - CI). Sub-stages for Missing (Lost, Stolen) and Defective (In Stock, In Transit) are also shown. Management responsibilities like Strategic Portfolio Mgmt, Procurement, Asset Mgmt, and CMDB Mgmt are mapped to their respective stages.

## **Change Control Board (CCB)**

Form a Configuration Control Board (CCB). The CCB is a team of people that ensures your CMDB delivers continuous value. This team sets direction and makes decisions on what is needed to ensure your CMDB can support your organization’s strategic initiatives and determine if the CMDB is ready for utilization.

![Common Service Data Model diagram showing the relationships between domains (Foundation, Design, Build, Manage Technical Services, Sell / Consume) and various data objects like SDLC Component, Business Capability, Information Object, and Service Portfolio. It also includes a Foundation section with Business Process, Contracts, Products (Models), CMDB Group, Locations, Groups, Users, Company, Business Unit, Department, and Life Cycle. The diagram is divided into four main functional areas: Manage Technical Services, Design, Sell / Consume, and Build.](fc46871d72c65d3381d9201646d23439_img.jpg)

**Common Service Data Model**

**Domains**

- Foundation
- Design
- Build
- Manage Technical Services
- Sell / Consume

**Foundation**

**Business Process:** A method of related steps that stakeholders take to achieve a business goal.

**CMDB Group:** A collection of CIs based on the results of saved Query Builder queries, encoded queries, or manual entries.

**Product Models:** Specific versions or configurations of products used for managing and tracking through various ServiceNow platform applications.

**Contracts:** Contracts contain detailed information such as contract number, start and end dates, active status, terms and conditions statements, documents, renewal information, and financial terms.

**Common Data:** Shared data that is prevalent throughout the Now Platform.

**Lifecycle:** The Life Cycles are standard fields and values for tracking life cycle stages and stage statuses for Products, Assets, Contracts, CIs, Locations, and more.

**Design**

**Business Capability:** A high level capability required by the organization to execute its business model.

**Business Application:** A purchased, or internally developed application used to support a business capability.

**Information Object:** Describes the type of data that is being interchanged between the business application and the database serving it.

**Build**

**SDLC Component:** The SDLC Component is a configuration item that represents a unique development effort.

**Manage Technical Services**

**Application Service:** Logical representation of a deployed system or application stack.

**Technical Service:** Published to service owners and typically underpins one or more business services. A Technical Service may have an operational view made up of one or more Technical Service Offerings.

**Technical Service Offering:** Stratification of the Technical Service into options, including localization/geography, environment, pricing, availability, capability, support group (INCIDENT), technical approval group (CHANGE) and packaging options.

**Dynamic CI Group:** a dynamic grouping of configuration items (CIs), based on results of CMDB Groups queries.

**Configuration Item (CI):** Physical and logical components of an infrastructure that are currently, or soon will be, under configuration management.

**Sell / Consume**

**Service Portfolio:** Hierarchical categorization of business services (Products & Services) that define strategic business value and facilitate the management of their life cycle.

**Business Service:** Published to business users and it typically underpins one or more business capabilities. Business services are often orderable by business users. Business users are able to select the desired offering and service commitment levels via a Service Catalog.

**Business Service Offering:** Stratification of the Business Service into options, including localization/geography, pricing, availability, capability, criticality, business approval group (CHANGE), and packaging options.

**Request Catalogue:** Consumable catalogue view of available business & technical products, services, service commitment options, and offerings.

Common Service Data Model diagram showing the relationships between domains (Foundation, Design, Build, Manage Technical Services, Sell / Consume) and various data objects like SDLC Component, Business Capability, Information Object, and Service Portfolio. It also includes a Foundation section with Business Process, Contracts, Products (Models), CMDB Group, Locations, Groups, Users, Company, Business Unit, Department, and Life Cycle. The diagram is divided into four main functional areas: Manage Technical Services, Design, Sell / Consume, and Build.

To operationalize and maintain the health of the CMDB, ServiceNow has created three of pillars to success. At the highest level each pillar focuses on a key customer pain point.

- **First is Ingestion of CMDB data:** This is how the CMDB is populated and the data is identified and reconciled. Automate as much as possible the flow of data into the CMDB at a frequency that supports your stated use cases
- **Second is Governance of the data:** Getting the data in is just the beginning of your CMDB journey. Next is the management and upkeep of the data to maintain a healthy CMDB and gain value from the data.
- **Third is Insight into the data in the CMDB:** How do you visualize and utilize this data across the platform?

![Diagram showing three pillars of CMDB success: Ingest, Governance, and Insight, each with a list of tools and features, all pointing towards a central 'CMDB Workspace'.](997233d405f0d4b89ddeb7683e047f66_img.jpg)

**Ingest**

- ServiceNow Discovery
- Service Mapping
- Agent Client Collector
- Service Graph Connectors
- IntegrationHub ETL
- Import Sets

**Governance**

- CI Class Manager
- CMDB Health Dashboard
- Data Manager
- Duplicate CI Remediator
- De-duplication Templates

**Insight**

- CMDB Query Builder
- Unified Map
- Intelligent Search
- CMDB and CSDM Data Foundations Dashboard

**CMDB Workspace**

Diagram showing three pillars of CMDB success: Ingest, Governance, and Insight, each with a list of tools and features, all pointing towards a central 'CMDB Workspace'.

## ServiceNow CMDB Data Population & Discovery Methods (Ingestion)

ServiceNow provides multiple approaches to populate and maintain the CMDB, ranging from automated discovery to integrations and data imports. Each method serves a specific purpose and has licensing and configuration considerations.

### 1. ServiceNow Discovery (Horizontal / Agentless, IP-based discovery)

- Automatically discovers infrastructure (servers, network devices, applications).
- Populates the CMDB and maps dependencies between components.
- **License:** Paid (ITOM Visibility).
- **Note:** Discovered data should be enriched with non-discoverable attributes (e.g., support group, managed by).
- **Schedule based; not real-time.**
- It uses **probes and sensors** to determine the device type.

#### MID Server:

- The **MID Server (Management, Instrumentation, and Discovery Server)** is deployed inside the organization's **trusted network**.
- It acts as a **secure bridge** between the ServiceNow instance and internal systems that are not directly accessible due to firewalls or network restrictions.
- All communication between ServiceNow and the MID Server is **encrypted**.
- ServiceNow sends **probes** to the MID Server; the MID Server executes them and returns results, which **sensors** use to update the **CMDB**.
- Discovery is **agentless** and uses standard protocols:
  - **WMI** for Windows
  - **SSH** for Linux/Unix
  - **SNMP** for network devices
- The MID Server ensures **secure, scalable Discovery** without exposing internal systems to the internet.

✓ Key takeaway: *ServiceNow never directly connects to internal devices—everything goes through the MID Server.*

#### Discovery Schedules:

- **Discovery Schedules** define *when, what, and where* Discovery runs.
- Used for **horizontal Discovery** (network-based scanning).
- Specify:

- **IP ranges / scope**
- **Schedule timing**
- **Assigned MID Server(s)**
- Can target **on-prem environments** or **cloud service accounts**.
- Schedules trigger Discovery using **probes, sensors, and patterns** to identify and update **CIs in the CMDB**.

#### **Discovery Admin Workspace (Schedules Page)**

- Central hub to **monitor and manage Discovery operations**.
- Provides **real-time visibility** into Discovery activity and performance.
- Key reports include:
  - **Schedules by location** (map)
  - **Total schedules** (last 24 hours)
  - **Errors by category**
  - **Total Discovery attempts** (completed vs canceled)

✓ Key takeaway: *Discovery Schedules control horizontal Discovery execution and are monitored through the Discovery Admin Workspace.*

#### **Types of Discovery:**

- **Network Discovery**
  - Identifies **internal IP address ranges**.
  - Not required if IP ranges are already known.
- **CI Discovery**
  - Discovers **devices, servers, and applications**.
  - **Most commonly used** Discovery type.
- **Cloud Discovery**
  - Discovers **AWS and Azure resources**.
  - Uses cloud credentials and APIs.
- **Serverless Discovery**
  - Discovers **applications without discovering the host first**.
  - **Pattern-based** and does not rely on traditional host discovery.

✓ Key takeaway: *All are forms of horizontal Discovery, each targeting different environments and use cases.*

#### Limiting Discovery Data:

- **Improves data accuracy**
  - Avoids populating the CMDB **with low-priority** or irrelevant data.
  - Establishes a strong foundation with high-quality CIs.
- **Prevents CMDB data overload**
  - Reduces clutter caused by unnecessary Discovery results.
  - Keeps the CMDB clean and maintainable.
- **Faster initial deployment**
  - Fewer devices scanned → quicker Discovery cycles.
  - Enables a usable CMDB early, with gradual expansion later.
- **Simplifies CMDB management**
  - **Focuses on key CI classes (e.g., servers, critical applications).**
  - Ensures data is immediately relevant to business needs.
- **Better stakeholder buy-in**
  - Quick wins with accurate data build trust.
  - Encourages support for broader Discovery adoption later.

✓ Key takeaway: *Start small, discover what matters first, then expand Discovery incrementally.*

#### Discovery Ranges:

**Discovery ranges** define which IP addresses ServiceNow Discovery scans.

- **You can include or exclude specific IP ranges** in a Discovery schedule.
- **Broad Ranges (Subnets)**
- Example:
  - 192.168.0.0/24
  - 10.11.128.192/26
- Includes **network and broadcast addresses**.
- Scans a **large number of IPs**, which may cause:
  - Data overload
  - Redundant or irrelevant CIs
  - Discovery errors
- **Not recommended** during initial implementation.
- Best practice: **Do not exceed /16** (~65,000 IPs); split into smaller ranges if needed.