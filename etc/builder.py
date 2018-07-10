# Support for autosave/restore.  This needs to be tied into record support
# for programmer suppport.

import os.path, sys
from iocbuilder import Device, Substitution, Call_TargetOS
from iocbuilder.recordbase import Record
from iocbuilder import iocwriter
from iocbuilder.arginfo import *
from iocbuilder.iocinit import quote_IOC_string, iocInit

__all__ = ['Autosave', 'SetAutosaveServer']


class _AutosaveFile(Substitution):
    Arguments = ('device', 'file',)
    TemplateFile = 'dlssrfile.template'


class _AutosaveStatus(Substitution):
    Arguments = ('device', 'name')
    TemplateFile = 'dlssrstatus.template'


class Autosave(Device):
    LibFileList = ['autosave']
    DbdFileList = ['asSupport']

    # Default uid and gid authentications for vxWorks
    DEFAULT_UID = 37134     # User epics_user
    DEFAULT_GID = 500       # Group dcs

    def __init__(self,
            iocName, debug=0, skip_1=False, server=None, ip=None,
            path=None, name=None, vx_uid=DEFAULT_UID, vx_gid=DEFAULT_GID,
            bl=False):
        self.__super.__init__()
        if path is not None:
            self.SetAutosaveServer(server, ip, path)

        self.autosave_dir = 'data'
        self.__iocName = iocName
        self.__debug = debug
        self.skip_1 = skip_1
        self.__rule_added = False
        self.vx_uid = vx_uid
        self.vx_gid = vx_gid
        self.bl = bl
        if self.bl:
            # need directoryWait or nfsMountWait
            from iocbuilder.modules.utility import Utility
            Utility()

        if iocName is not None:
            _AutosaveFile(device = iocName, file = '0')
            _AutosaveFile(device = iocName, file = '1')
            _AutosaveFile(device = iocName, file = '2')

            _AutosaveStatus(device = iocName, name = name)

        # The autosaves are recorded as a list of dictionaries of sets of field
        # names indexed by record name and pass number:
        #   field_set = self.autosaves[pass_number][record_name]
        # Only passes 0, 1 and 2 are supported.
        self.autosaves = [{}, {}, {}]
        # Five separate Autosave functions are added to each record for marking
        # fields for autosaving.  The most general is
        #   record.AutosaveField(autosave_pass, fields...)
        # and all the rest are variations:
        #   .Autosave(...)  = .Autosave0(...) = .AutosavePass(0, ...)
        #   .Autosave1(...) = .AutosaveField(1, ...)
        #   .Autosave2(...) = .AutosaveField(2, ...)
        Record.AddMetadataHook(
            self.PrintMetadata,
            Autosave  = self.__AutosaveField(0),
            Autosave0 = self.__AutosaveField(0),
            Autosave1 = self.__AutosaveField(1),
            Autosave2 = self.__AutosaveField(2),
            AutosavePass = self.AutosaveField)

        iocwriter.AddDbMakefileHook(self.DbMakefileHook)


    ArgInfo = makeArgInfo(__init__,
        iocName = Simple('IOC Name EPICS prefix'),
        debug   = Simple('Debug level', int),
        skip_1  = Simple('If True, don\'t restore file 1', bool),
        server  = Simple('NFS server name (vxWorks bl=False only)'),
        ip      = Simple('NFS server ip (vsWorks only), or blgateway ip if bl=True'),
        path    = Simple(
            'Root of path to put autosave files in, '
            'ioc name will be appended to this'),
        name    = Simple('Object name'),
        vx_uid  = Simple('UID of vxWorks autosave user', int),
        vx_gid  = Simple('GID of vxWorks autosave group', int),
        bl      = Simple(
            'If True, then assume we are on a beamline, that ip=blgateway '
            'machine ip and make sure the relevant storage server or directory '
            'is up before booting. ', bool))


    # Called during record output, we add the autosave metadata
    def PrintMetadata(self, record):
        for pass_number, autosaves in enumerate(self.autosaves):
            for field in autosaves.get(record.name, []):
                print '#%% autosave %d %s' % (pass_number, field)

    # Called during record building to mark individual fields on records to
    # be autosaved.
    def AutosaveField(self, record, pass_number, *fieldnames):
        '''Marks all named fields of the given record to be autosaved.'''
        fieldset = self.autosaves[pass_number].setdefault(record.name, set())
        for fieldname in fieldnames:
            record.ValidFieldName(fieldname)
            fieldset.add(fieldname)

    def __AutosaveField(self, pass_number):
        return lambda record, *fieldnames: \
            self.AutosaveField(record, pass_number, *fieldnames)

    def Initialise_vxWorks(self):
        assert self.AutosaveIp, "Autosave IP must be set"
        if self.bl:
            assert self.AutosavePath.startswith("/dls_sw/"), \
                'Beamline autosave path must start with /dls_sw/'
            print 'ASPATH = "%s/%s"' % (self.AutosavePath[8:], self.__iocName)
            assert self.AutosaveIp.endswith(".254"), 'ip "%s" should end in .254' % self.AutosaveIp
            print 'BLGATEWAY = "%s"' % self.AutosaveIp
            print '< /dls_sw/prod/etc/init/autosave_mount'
        else:
            assert self.AutosaveServer, "Autosave server must be set"
            print 'hostAdd "%s", "%s"' % (self.AutosaveServer, self.AutosaveIp)
            print 'nfsAuthUnixSet "%s", %d, %d, 0, 0' % (
                self.AutosaveServer, self.vx_uid, self.vx_gid)
            print 'save_restoreSet_NFSHost "%s", "%s"' % (
                self.AutosaveServer, self.AutosaveIp)
            print 'set_savefile_path "%s/%s"' % (
                self.AutosavePath, self.__iocName)
        print 'requestfilePath = malloc(256)'
        if iocInit.substitute_boot:
            print 'strcpy requestfilePath, "${INSTALL}/%s"' % \
                self.autosave_dir
        else:
            print 'sprintf requestfilePath, "%%s/%s", top' % \
                self.autosave_dir
        print 'set_requestfile_path requestfilePath'

    def Initialise_linux(self):
        if self.bl:
            # make sure the autosave directory exists
            print 'directoryWait("%s/%s", 10)' % (self.AutosavePath, self.__iocName)
        if iocInit.substitute_boot:
            print 'set_requestfile_path "${INSTALL}/"%s' % \
                quote_IOC_string(self.autosave_dir)
        else:
            print 'set_requestfile_path "${TOP}/"%s' % \
                quote_IOC_string(self.autosave_dir)
        print 'set_savefile_path "%s/%s"' % (
            self.AutosavePath, self.__iocName)

    def Initialise_windows(self):
        self.Initialise_linux()

    def Initialise_win32(self):
        self.Initialise_linux()

    def Initialise(self):
        print '# Autosave and restore initialisation'
        assert self.AutosavePath, "Autosave path must be set"
        Call_TargetOS(self, 'Initialise')
        print
        print 'save_restoreSet_status_prefix "%s"' % self.__iocName
        print 'save_restoreSet_Debug %d' % self.__debug
        print 'save_restoreSet_NumSeqFiles 3'
        print 'save_restoreSet_SeqPeriodInSeconds 600'
        print 'save_restoreSet_DatedBackupFiles 1'
        print 'save_restoreSet_IncompleteSetsOk 1'
        print 'set_pass0_restoreFile "%s_0.sav"' % self.req_prefix
        if not self.skip_1:
            print 'set_pass0_restoreFile "%s_1.sav"' % self.req_prefix
            print 'set_pass1_restoreFile "%s_1.sav"' % self.req_prefix
        print 'set_pass1_restoreFile "%s_2.sav"' % self.req_prefix


    def PostIocInitialise(self):
        print 'create_monitor_set "%s_0.req",  5, ""' % self.req_prefix
        print 'create_monitor_set "%s_1.req", 30, ""' % self.req_prefix
        print 'create_monitor_set "%s_2.req", 30, ""' % self.req_prefix


    def DbMakefileHook(
            self, makefile, ioc_name, db_filename, expanded_filename):
        # Called when a .db file is added
        if not self.__rule_added:
            self.__rule_added = True
            self.req_prefix = ioc_name

            fnames = []
            # have a db file
            if db_filename and any(self.autosaves):
                fnames.append('../%s' % db_filename.replace(ioc_name, '%'))
            # have a substitutions file
            if expanded_filename:
                fnames.append(expanded_filename.replace(ioc_name, '%'))

            if fnames:
                makefile.AddRule(
                    _REQ_DB_RULE % dict(
                        dependencies = ' '.join(fnames),
                        parser = _EPICSPARSER))

                makefile.AddLine('ifeq (linux, $(findstring linux, $(T_A)))')

                for n in range(3):
                    makefile.AddLine('DATA += %s_%d.req' % (self.req_prefix, n))

                makefile.AddLine('endif')


    @classmethod
    def SetAutosaveServer(cls, server, ip, path):
        cls.AutosaveServer = server
        cls.AutosaveIp = ip
        cls.AutosavePath = path

SetAutosaveServer = Autosave.SetAutosaveServer

# Rule to build all three .req files by postprocessing the corresponding .db
# file.
_REQ_DB_RULE = '''
%%_0.req %%_1.req %%_2.req: %(dependencies)s
\t%(parser)s -s as -r $* $^
\ttouch $*_0.req $*_1.req $*_2.req
'''
_EPICSPARSER = 'epicsparser.py'
