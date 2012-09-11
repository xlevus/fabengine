import os
import tempfile
from shutil import rmtree

from fabric.api import local, settings, hide
from fabric.tasks import Task

__all__ = ['bundle_packages', 'dev_appserver','test','show_config',
    'fix_virtualenv_paths', 'update', 'update_indexes', 'update_queues',
    'update_dos', 'update_cron', 'vacuum_indexes']

def find_appengine():
    import subprocess
    p = subprocess.Popen(['which','dev_appserver.py'], stdout=subprocess.PIPE)
    path = p.stdout.read().strip()
    if os.path.islink(path):
        path = os.path.realpath(path)
    return os.path.dirname(path)

TRUE = ('true','t','y','1')

CONFIG = {}

GAE_CUSTOMISE = """
def fix_sys_path():
    try:
        import sys, os
        from dev_appserver import fix_sys_path, DIR_PATH
        fix_sys_path()
        # must be after fix_sys_path
        # uses non-default version of webob
        webob_path = os.path.join(DIR_PATH, 'lib', 'webob_1_1_1')
        sys.path = [webob_path] + sys.path
    except ImportError:
        pass
"""

def config(root, gae_path=None, dev_appserver=None, appcfg=None):
    global CONFIG
    CONFIG['ROOT'] = os.path.abspath(root)
    CONFIG['GAE_PATH'] = gae_path or find_appengine()
    CONFIG['DEV_APPSERVER'] = dev_appserver or os.path.join(
            CONFIG['GAE_PATH'], 'dev_appserver.py')
    CONFIG['APPCFG'] = appcfg or os.path.join(CONFIG['GAE_PATH'], 'appcfg.py')

class ShowConfig(Task):
    """Shows Fabengine's config"""
    name = 'show_config'

    def run(self):
        for x in CONFIG.iteritems():
            print "%s: %s" % x

class BundlePackages(Task):
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

    def zip_packages(self):
        unzipped = False
        pkgs = local("pip zip -l --path=%s" % self.temp_dir, capture=True)

        for ln in pkgs.splitlines():
            ln = ln.strip()

            if ln.startswith("Unzipped"):
                unzipped = True
                continue

            # Skip through all lines until we get to Unzipped section
            if not unzipped:
                continue

            package, discards = ln.split(" ", 1)

            local("pip zip --no-pyc --path=%s %s" % (self.temp_dir, package))

    def fix_pth_paths(self):
        # Our .pth files were pointing to /tmp/xyz. fix them to be relative.
        for filename in os.listdir(self.package_dir):
            if filename.endswith('.pth'):
                with open(os.path.join(self.package_dir, filename), 'r+') as f:
                    contents = f.read()
                    f.seek(0)
                    f.truncate()
                    f.write(contents.replace(self.temp_dir, '.'))

    def run(self, requirements='requirements.txt', dest='packages',
            archive='True'):

        temp = tempfile.mkdtemp(prefix="fabengine")
        try:
            self.temp_dir = os.path.join(temp, 'lib/python2.7/site-packages')
            self.package_dir = os.path.join(CONFIG['ROOT'], dest)

            # fix pythonpath for --prefix install option
            os.environ['PYTHONPATH'] = self.temp_dir

            local("""pip install --upgrade --install-option="--prefix=%s" -r %s""" % (
                temp, requirements))

            if archive.lower() in TRUE:
                self.zip_packages()

            local("mv %s %s" % (self.temp_dir, self.package_dir))

            self.fix_pth_paths()
        finally:
            print "Cleaning up temp dir '%s'" % temp
            rmtree(temp)


class DevAppserver(Task):
    """
    Runs the development appserver.

    First two arguments are host and port. Any keyword arguments are forwarded
    to dev_appserver.py.
    """
    name = 'dev_appserver'

    def run(self, host=None, port=None, kill='False', **kwargs):
        if kill.lower() in TRUE:
            local("ps ax|grep 'appengine/dev_appserver.py'|grep -v grep|awk {'print $1'}|xargs kill -9")

        args = [CONFIG['DEV_APPSERVER']]
        args += ['--'+k for k in kwargs.keys()]

        if host:
            args.append('-a %s' % host)
        if port:
            args.append('-p %s' % port)

        args.append(CONFIG['ROOT'])
        local(" ".join(args))


class Test(Task):
    """
    Run Nosetests.

    All arguments and keyword arguments except for `with_sandbox` are
    forwarded to nose.

    When `with_sandbox` omitted provided, tests are run outside of the
    appengine sandbox.
    """
    name = 'test'

    def run(self, *args, **kwargs):
        cmd = ['nosetests', '--with-gae',
            '--gae-lib-root=%s' % CONFIG['GAE_PATH']]

        if not kwargs.get('with-sandbox'):
            cmd.append('--without-sandbox')
        else:
            del kwargs['with-sandbox']

        for k,v in kwargs.iteritems():
            if k.startswith('--'):
                cmd.append("%s=%s" % (k,v))

        cmd.extend(args)

        with settings(warn_only=True):
            with hide('warnings'):
                local(" ".join(cmd))

class FixVirtualenvPaths(Task):
    """
    Applies some permanent path manipulation to make the virtualenv use appengine's paths.

    See:
    https://schettino72.wordpress.com/2010/11/21/appengine-virtualenv/
    """
    name = 'fix_virtualenv_paths'

    def run(self):
        import sys

        env = os.environ.get('VIRTUAL_ENV')
        assert env

        for path in sys.path[::-1]:
            if path.startswith(env) and path.endswith('site-packages'):
                break

        with open(os.path.join(path, 'gaecustomise.py'),'w') as gaecustom:
            gaecustom.write(GAE_CUSTOMISE)

        with open(os.path.join(path, 'gae.pth'), 'w') as gaepth:
            gaepth.write(CONFIG['GAE_PATH'])
            gaepth.write("\nimport gaecustomise; gaecustomise.fix_sys_path()")


class AppCFGTask(Task):
    """Base task for appcfg.py commands."""

    name = None

    def get_cmd(self, *args, **kwargs):
        cmd_args = [CONFIG['APPCFG'], self.name, CONFIG['ROOT']]

        for a in args:
            cmd_args.append("-%s" % a)

        for k,v in kwargs.iteritems():
            cmd_args.append("--%s=%s")

        return cmd_args

    def run(self, *args, **kwargs):
        local(" ". self.get_cmd(*args, **kwargs))

class Update(AppCFGTask):
    """Upload code to appengine"""
    name = 'update'

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

