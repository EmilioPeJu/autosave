#Makefile at top of application tree
TOP = .
include $(TOP)/configure/CONFIG
DIRS += configure asApp iocBoot
asApp_DEPEND_DIRS   = configure
iocBoot_DEPEND_DIRS = asApp
DIRS := $(DIRS) $(filter-out $(DIRS), $(wildcard etc))
# Comment out the following line to disable building of example iocs
DIRS := $(DIRS) $(filter-out $(DIRS), $(wildcard iocs))
include $(TOP)/configure/RULES_TOP
