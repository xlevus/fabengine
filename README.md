A collection of appengine related fabfile commands.

Usage
=====

 1. Install dependencies

        pip install https://github.com/xlevus/fabengine/zipball/master

 2. Create fabfile:

        import fabengine

Configuration
=============

Configuration can be done through the fabengine.config function.::

    fabengine.config(root=os.path.join(os.path.dirname(__file__),'my_project'))

`fabengine.config` takes three arguments:

  - `root`: The root path of your appengine project. (Required)
  - `gae_path`: The path to your appengine SDK. fabengine will attempt to find this
    automatically by looking for dev_appserver.py on your `PATH`. (Optional)
  - `dev_appserver`: The path to `dev_appserver.py`. fabengine will use 
    `<gae_path>/dev_appserver.py` if it is not provided. (Optional)
  - `appcfg`: The path to `appcfg.py`. fabengine will use `<gae_path>/appcfg.py` if it not
    provided. (Optional)


Per-command defaults
--------------------
Per-Command defaults can be provided through `fabengine.COMMAND.set_default_args`. These can be 
overridden through the command line.

    fabengine.bundle_packages.set_default_args(
        requirements='../requirements.txt', archive=False)



Commands
========

By default, all commands are run from within your projects `root` (as defined by fabengine.config).

Command arguments are forwarded in the following format:
 * Positional arguments become '--VALUE'
 * Keyword arguments become '--KEY=VALUE'

e.g.
    fab fabengine.some_command:foo,bar=baz
becomes
    some_command --foo --bar=baz


`bundle_packages`
-----------------
Creates zipimport compatible archives from your `requirements.txt` file into a packages folder.
Args:

 * `requirements` - Path of requirements.txt file. Default: requirements.txt
 * `dest` - Destination path of packages folder. Default: `packages`
 * `archive` - Flag to toggle compression of archives. Default: `True`


`dev_appserver`
---------------
Runs `dev_appserver.py` on config root.

    fab fabengine.dev_appserver:use_sqlite,port:8081 
    --> 
    dev_appserver.py --use_sqlite --port=8081 my_project_root


`test`
------
Runs nosetests with GAE parameters. Arguments are passed to nosetests the same way as `dev_appserver`.

By default nose is called `--without-sandbox`. This can be changed by calling `fabengine.nose.set_default_args()`.

To Specifiy which module or file to test, use the MODULE keyword argument.

e.g.

    fab fabengine.test:stop,processes:2,MODULE:testthis.py
    -->
    nosetests --with-gae --gae-lib-path=GAE_PATH --stop --processes=2 testthis.py


Appcfg.py Commands
------------------
The following convenience tasks for appcfg.py commands are provided:

    update
    update_indexes
    update_queues
    vacuum_indexes
    update_dos
    update_cron


Additional Commands
-------------------

 * **show_config** - Shows the internal fabengine config.

 * **fix_virtualenv_paths** - Applies some permanent path manipulation to the current virtualenv
   to fix loading of libraries bundled with the appengine sdk.

TODO
----

 * Add missing appcfg.py commands.
 * Copy LICENSE, README, etc from package-source into bundled packages.

