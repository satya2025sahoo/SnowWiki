# CMDB and CSDM

The CMDB is the database while the Common Service Data Model (CSDM) is the data model. The data model helps determine where to record items in the CMDB, and what relationships are important to drive business value.

## Configuration Item (CI)

Physical and logical components of an infrastructure that needs to be managed to deliver a product or service and are currently, or soon will be, under configuration management. For example, a network device, a server, an application, a delivery truck, or service.

## Attribute

Information that further describes a CI such as a name, serial number, manufacturer, operating system.

## Relationship Type

Include the relationships between configuration items. For example, a web application might read data from a specific database, which in turn might depend on a piece of underlying hardware.

## Class

Describes a table that contains and represents a specific type or group of CIs that share common attributes such as a Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, Animal etc.

## Configuration Management Database (CMDB)

A database used to store configuration records throughout their lifecycle. The Configuration Management System maintains one or more CMDBs, and each CMDB stores attributes of CIs, and relationships with other CIs.

## Base Table

The core Configuration Item [cmdb_ci] table, which stores the basic attributes of all the CIs. All configuration item classes extend from this table including all hardware and applications.

## CI Reclassification

A CI whose class has been upgraded, downgraded, or switched. An example of an upgraded CI is a Server record that was upgraded from the Server `[cmdb_ci_server]` class to the Windows Server `[cmdb_ci_win_server]` class.

## Parent and Child Class

A table that extends another table is called a child class, and the table it extends is the parent class. A table can be both a parent and child class, extending and providing extensions for other tables. For example, the Server table extends the Computer table and the Windows Server table extends the Server table, thus making the Server table both a parent and child class.

## Asset vs. CI

On the Now platform, when creating a hardware asset, a corresponding CI will be automatically created, or when a CI is discovered for the first time and inserted into the CMDB, a corresponding asset record will be automatically created. The asset and the CI are connected throughout the CI/Asset lifecycle.

### Asset

- Often starts during the procurement process, but may be created when a discovery tool finds the CI for the first time.
- Is part of the financial lifecycle.

### Configuration Item (CI)

- Often starts when a discovery tool finds the CI for the first time, but may be created during the procurement process.
- Is part of the technical operations.

## Common Services Data Model (CSDM)

Represents a standard and shared set of service‑related definitions across ServiceNow products and the NOW platform that enables and supports true service level reporting while providing prescriptive guidance on service modeling within the CMDB. These service‑related definitions span the ServiceNow® product portfolio and the Now Platform®.

### Application Service

A set of interconnected applications and hosts which are configured to offer a service to the organization. Application services can be internal, like an organization email system.

Application services can be internal, like an organization email system, or customer-facing, like an organization website.

#### Application
Applications that comprise an application service as configuration items (CIs).  
The various applications and the relationships between them that comprise an application service are stored in the CMDB (e.g., Tomcat, Apache, Microsoft SQL, Oracle, IIS).

#### DevOps
Consists of developers who build applications and the operations groups who deploy and maintain them within an enterprise.  
In a DevOps environment, these two groups are combined into one to work more effectively together, accelerating and improving service delivery.

#### Principal Class
Principle classes can be configured to limit the CI classes that display in the Configuration Item fields on incident, problem, and change records.

#### Logical CI
Logical CIs do not take up physical space. They perform specific functions that require physical components to operate.  
Examples include Service Offering, Service, and Business Application, which are manually entered into the CMDB.

#### Examples
1️⃣ **Business Application**  
   • Logical CI: “Microsoft Teams” (the collaboration/chat app used by employees)

#### Examples

1️⃣ **Business Application**  
   • Logical CI: “Microsoft Teams” (the collaboration/chat app used by employees)

2️⃣ **Service**  
   • Logical CI: “Corporate Email Service”  
   • Physical CIs it depends on:  
     - Exchange Server or Office 365 backend  
     - Mail servers  
     - Storage for email data  
     - Network connections for email delivery

3️⃣ **Service Offering**  
   • Logical CI: “VPN Access for Remote Employees”  
   • Physical CIs it depends on:  
     - VPN servers  
     - Firewalls  
     - Network links to the corporate office

4️⃣ **Other Examples**  
   • Logical CI: “HR Payroll System”  
     - Depends on: Payroll application servers, database servers, authentication servers.  
   • Logical CI: “Customer‑Facing Website”  
     - Depends on: Web servers, application servers, load balancers, content delivery network.

💡 **Tip:** A simple way to think of it:  
Logical CI = What the business sees / uses  
Physical CI = What actually runs it behind the scenes

**Foundation data:**

## Configuration Management Database (CMDB)

### Not part of the CMDB, but referenced in the CI records.

One of the most important and challenging aspects of CMDB design is selecting the appropriate CI classes, levels, attributes, and relationships to be used as part of a CMDB implementation. During a CMDB health check, ServiceNow examines the number of custom classes and attributes created and assesses whether these custom attributes are established at the correct level. ServiceNow provides a free store application called **CMDB CI Class Models** that can be installed on a ServiceNow instance to obtain a wide range of additional classes that are not provided in a base instance.

#### Automated discovery tools by SN

- ServiceNow Discovery  
- Service Mapping  
- Agent Client Collector

---

# Configuration and Asset Management Lifecycles

An asset becomes a CI (Configuration Item) when it is deployed and remains a CI throughout its lifecycle until it is returned to stock or disposed of. As illustrated in the diagram, Configuration Management and IT Asset Management are distinct, yet complementary practices.

## Change Control Board (CCB)

Form a Configuration Control Board (CCB). The CCB is a team of people that ensures your CMDB delivers continuous value. This team sets direction and makes decisions on what is needed to ensure your CMDB can support your organization’s strategic initiatives and determine if the CMDB is ready for utilization.

## CMDB Health Pillars

- **Ingestion of CMDB data**: This is how the CMDB is populated and the data is identified and reconciled. Automate as much as possible the flow of data into the CMDB at a frequency that supports your stated use cases.
- **Governance of the data**: Getting the data in is just the beginning of your CMDB journey. Next is the management and upkeep of the data to maintain a healthy CMDB and gain value from the data.
- **Insight into the data in the CMDB**: How do you visualize and utilize this data across the platform?

## CMDB Health Pillars

- **Ingestion of CMDB data**: This is how the CMDB is populated and the data is identified and reconciled. Automate as much as possible the flow of data into the CMDB at a frequency that supports your stated use cases.
- **Governance of the data**: Getting the data in is just the beginning of your CMDB journey. Next is the management and upkeep of the data to maintain a healthy CMDB and gain value from the data.
- **Insight into the data in the CMDB**: How do you visualize and utilize this data across the platform?

### ServiceNow CMDB Data Population & Discovery Methods (Ingestion)

1. **ServiceNow Discovery (Horizontal / Agentless, IP-based discovery)**
   - Automatically discovers infrastructure (servers, network devices, applications).
   - Populates the CMDB and maps dependencies between components.
   - License: Paid (ITOM Visibility).
   - Note: Discovered data should be enriched with non-discoverable attributes (e.g., support group, managed by).
   - Schedule based; not real-time.
   - It uses probes and sensors to determine the device type.

#### MID Server
- The MID Server (Management, Instrumentation, and Discovery Server) is deployed inside the organization’s trusted network.
- It acts as a secure bridge between the ServiceNow instance and internal systems that are not directly accessible due to firewalls or network restrictions.
- All communication between ServiceNow and the MID Server is encrypted.
- ServiceNow sends probes to the MID Server; the MID Server executes them and returns results, which sensors use to update the CMDB.
- Discovery is agentless and uses standard protocols:
  - WMI for Windows
  - SSH for Linux/Unix
  - SNMP for network devices
- The MID Server ensures secure, scalable Discovery without exposing internal systems to the internet.
- ✔ Key takeaway: ServiceNow never directly connects to internal devices—everything goes through the MID Server.

#### Discovery Schedules
- Discovery Schedules define when, what, and where Discovery runs.
- Used for horizontal Discovery (network-based scanning).
- Specify:

