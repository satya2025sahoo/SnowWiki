The CMDB is the database while the Common Service Data Model (CSDM) is the data model. The data model helps determine where to record items in the CMDB, and what relationships are important to drive business value.

#### Configuration Item (CI)

Physical and logical components of an infrastructure that needs to be managed to deliver a product or service and are currently, or soon will be, under configuration management. For example, a network device, a server, an application, a delivery truck, or service.

#### Attribute

Information that further describes a CI such as a name, serial number, manufacturer, operating system.

### Relationship Type

Include the relationships between configuration items. For example, a web application might read data from a specific database, which in turn might depend on a piece of underlying hardware.

### Class

Describes a table that contains and represents a specific type or group of CIs that share common attributes such as a Windows Server, Linux Server, Printer, Virtual Machine, Vehicle, Animal etc.

# Configuration Management Database (CMDB)

A database used to store configuration records throughout their Lifecycle. The Configuration Management System maintains one or more CMDBs, and each CMDB stores attributes of CIs, and Relationships with other CIs.

## Base Table

The core Configuration Item [cmdb\_ci] table, which stores the basic attributes of all the CIs. All configuration item classes extend from this table including all hardware and applications.