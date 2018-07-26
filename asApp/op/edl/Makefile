TOP = ../../..
include $(TOP)/configure/CONFIG

# List here, the edl files to be be created using "velocity"
# Requires that you have the "*.v" file
#EDL_FROM_V += <name>.edl
#EDL_FROM_V += <name>.edl


DATA += $(patsubst ../%, %, $(wildcard ../*.edl))
DATA += $(patsubst ../%, %, $(wildcard ../*.gif))
DATA += $(patsubst ../%, %, $(wildcard ../*.png))

include $(TOP)/configure/RULES

