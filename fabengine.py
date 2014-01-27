import os
import tempfile
from shutil import rmtree
from functools import partial
import contextlib

from fabric.api import local, settings, hide, lcd, execute
from fabric.tasks import Task

__all__ = ['bundle_packages', 'dev_appserver','test','show_config',
    'fix_virtualenv_paths', 'update', 'update_indexes', 'update_queues',
    'update_dos', 'update_cron', 'vacuum_indexes', 'update_dispatch']

def find_appengine():
    try:
        import dev_appserver
        return os.path.dirname(dev_appserver.__file__)
    except ImportError:
        import subprocess
        p = subprocess.Popen(['which','dev_appserver.py'], stdout=subprocess.PIPE)
        path = p.stdout.read().strip()
        if os.path.islink(path):
            path = os.path.realpath(path)
        return os.path.dirname(path)

TRUE = ('true','t','y','1')
ISTRUE = lambda x: str(x).lower() in TRUE

CONFIG = {}

GAE_CUSTOMISE = """
import site
from dev_appserver import EXTRA_PATHS
for pth  in EXTRA_PATHS:
    site.addsitedir(pth)
"""

def config(root, modules=None, gae_path=None, dev_appserver=None, appcfg=None):
    global CONFIG

    CONFIG['MODULES'] = modules or ['app.yaml']
    CONFIG['ROOT'] = os.path.abspath(root)
    CONFIG['GAE_PATH'] = gae_path or find_appengine()
    CONFIG['DEV_APPSERVER'] = dev_appserver or os.path.join(
            CONFIG['GAE_PATH'], 'dev_appserver.py')
    CONFIG['APPCFG'] = appcfg or os.path.join(CONFIG['GAE_PATH'], 'appcfg.py')


def construct_cmd_params(*args, **kwargs):
    joiner = kwargs.pop('_joiner','=')

    def get_flag(name):
        if len(name) == 1:
            return '-'+name
        else:
            return '--'+name

    params = []
    params += [get_flag(a) for a in args]
    params += ['%s%s%s' % (get_flag(k),joiner,v) for k,v in kwargs.iteritems()]
    return params



class Before(object):
    """
    Context manager to facilitate running a command before another.

    All arguments from the main command are forwarded to the pre-runner.
    """

    @classmethod
    def create(cls, command):
        return partial(cls, command)

    def __init__(self, command, *args, **kwargs):
        self.command = command
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        execute(self.command, *self.args, **self.kwargs)


class After(Before):
    """
    Context manager to facilitate running a command after another.

    All arguments from the main command are forwarded to the post-runner.
    """

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        if value is None:
            execute(self.command, *self.args, **self.kwargs)


class FabengineTask(Task):
    def __init__(self, *args, **kwargs):
        self.default_arguments = ([],{})
        self.context_managers = []
        super(FabengineTask, self).__init__(*args, **kwargs)

    def set_default_args(self, *args, **kwargs):
        self.default_arguments[0].extend(args)
        self.default_arguments[1].update(kwargs)

    def run(self, *n_args, **n_kwargs):
        with lcd(CONFIG['ROOT']):
            args = set(self.default_arguments[0])
            args.update(n_args)

            kwargs = self.default_arguments[1].copy()
            kwargs.update(n_kwargs)
            with self._context_managers(*n_args, **n_kwargs):
                return self.run_fabengine(*list(args), **kwargs)

    def run_fabengine(self):
        raise NotImplementedError

    def _context_managers(self, *args, **kwargs):
        mgrs = []
        for mgr in self.context_managers:
            if callable(mgr):
                mgr = mgr(*args, **kwargs)
            mgrs.append(mgr)
        return contextlib.nested(*mgrs)

    def run_before(self):
        """Run command before another command"""
        return Before.create(self)

    def run_after(self):
        """Run command after another command"""
        return After.create(self)


class ShowConfig(FabengineTask):
    """Shows Fabengine's config"""
    name = 'show_config'

    def run_fabengine(self):
        for x in CONFIG.iteritems():
            print "%s: %s" % x


class BundlePackages(FabengineTask):
    """
    Bundles packages in requirements.txt into zipimport compatible archives.

    Takes two arguments. The name of the pip-requirements file (default:
    requirements.txt), and the destination package folder (default: packages).

    Packages can then be loaded with the following snippet:

        import sys, os
        package_dir = "packages"
        package_dir_path = os.path.join(os.path.dirname(__file__), package_dir)

        for filename in os.listdir(package_dir_path):
            if filename.endswith('.pth'):
                pth_file = os.path.join(package_dir_path, filename)
                with open(pth_file, 'r') as f:
                    package_path = os.path.join(package_dir_path, f.read().strip())
                    sys.path.insert(0, package_path)
        sys.path.insert(0, package_dir_path)
    """
    name= 'bundle_packages'

    def run_fabengine(self, requirements='requirements.txt', dest='packages',
            archive='True'):

        temp = tempfile.mkdtemp(prefix="fabengine")
        try:
            self.package_dir = os.path.join(CONFIG['ROOT'], dest)
            if not os.path.exists(self.package_dir):
                os.makedirs(self.package_dir)

            args = [
                "pip",
                "install",
                "-I",
                """--install-option="--install-lib=%s" """ % temp,
                "-r %s" % requirements,
            ]

            local(" ".join(args))

            with lcd(temp):
                if ISTRUE(archive):
                    local("zip -r0 %s ." % os.path.join(
                        self.package_dir,"fabengine_bundle.zip"))
                else:
                    local("cp -a * %s" % self.package_dir)

        finally:
            print "Cleaning up temp dir '%s'" % temp
            rmtree(temp)


class DevAppserver(FabengineTask):
    """
    Runs the development appserver. Positional arguments are forwarded as
    flags. Keyword arguments are forwarded as
    """
    name = 'dev_appserver'

    def run_fabengine(self, *args, **kwargs):
        cmd = [CONFIG['DEV_APPSERVER']]
        cmd.extend(construct_cmd_params(*args, **kwargs))
        cmd.extend(CONFIG['MODULES'])
        local(" ".join(cmd))


class Test(FabengineTask):
    """
    Run Nosetests.

    All arguments and keyword arguments except for `with_sandbox` are
    forwarded to nose.

    When `with_sandbox` omitted provided, tests are run outside of the
    appengine sandbox.
    """
    name = 'test'

    def __init__(self, *args, **kwargs):
        super(Test, self).__init__(*args, **kwargs)
        self.set_default_args('without-sandbox')

    def run_fabengine(self, *args, **kwargs):
        cmd = ['nosetests', '--with-gae',
            '--gae-lib-root=%s' % CONFIG['GAE_PATH']]

        module = kwargs.pop("MODULE",'')

        cmd.extend(construct_cmd_params(*args, **kwargs))
        cmd.append(module)

        with settings(warn_only=True):
            with hide('warnings'):
                local(" ".join(cmd))


class FixVirtualenvPaths(FabengineTask):
    """
    Applies some permanent path manipulation to make the virtualenv use appengine's paths.

    :param path: Path to google appengine.
    """
    name = 'fix_virtualenv_paths'

    def run_fabengine(self, path=None):
        import sys
        path = os.path.abspath(path or CONFIG['GAE_PATH'])
        print "Using sdk found in '%s'" % path

        env = os.environ.get('VIRTUAL_ENV')
        assert env

        for pth in sys.path[::-1]:
            if pth.startswith(env) and pth.endswith('site-packages'):
                break

        with open(os.path.join(pth, 'gaecustomise.py'),'w') as gaecustom:
            gaecustom.write(GAE_CUSTOMISE)

        with open(os.path.join(pth, 'gae.pth'), 'w') as gaepth:
            gaepth.write(path)
            gaepth.write("\nimport gaecustomise")


class AppCFGTask(FabengineTask):
    """Base task for appcfg.py commands."""

    name = None
    use_modules = False

    def get_cmd(self, *args, **kwargs):
        cmd_args = [CONFIG['APPCFG'], self.name]


        cmd_args.extend(construct_cmd_params(*args, **kwargs))

        if self.use_modules:
            cmd_args.extend(CONFIG['MODULES'])
        else:
            cmd_args.append(CONFIG['ROOT'])

        return cmd_args

    def run_fabengine(self, *args, **kwargs):
        local(" ".join(self.get_cmd(*args, **kwargs)))


class Update(AppCFGTask):
    """Upload code to appengine"""
    name = 'update'
    use_modules = True


class UpdateIndexes(AppCFGTask):
    """Update appengine indexes"""
    name = 'update_indexes'


class UpdateQueues(AppCFGTask):
    """Update appengine queues"""
    name = 'update_queues'


class VacuumIndexes(AppCFGTask):
    """Delete unused appengine indexes"""
    name = 'vacuum_indexes'


class UpdateDoS(AppCFGTask):
    """Update appengine DoS protection"""
    name = 'update_dos'


class UpdateCron(AppCFGTask):
    """Update appengine cron jobs"""
    name = 'update_cron'


class UpdateDispatch(AppCFGTask):
    """Update modules dispatch"""
    name = 'update_dispatch'


class DeleteVersion(AppCFGTask):
    """Delete version"""
    name = "delete_version"

class SetDefaultVersion(AppCFGTask):
    """Set Default Version"""
    name = "set_default_version"


show_config = ShowConfig()
bundle_packages = BundlePackages()
dev_appserver = DevAppserver()
test = Test()
fix_virtualenv_paths = FixVirtualenvPaths()
update = Update()
update_indexes = UpdateIndexes()
update_queues = UpdateQueues()
vacuum_indexes = VacuumIndexes()
update_dos = UpdateDoS()
update_cron = UpdateCron()
update_dispatch = UpdateDispatch()
delete_version = DeleteVersion()
set_default_version = SetDefaultVersion()

