fabengine
=========

A collection of appengine related fabfile commands.

Usage
-----

 1. Install dependencies

        pip install fabric nose NoseGAE

 2. Import fabengine

        import fabengine

 3. Configure fabengine paths.

        fabengine.config(root=os.path.join(os.path.dirname(__file__),'..'))

    `fabengine.config` takes three arguments:

   - `root`: The root path of your appengine project. (Required)
   - `gae_path`: The path to your appengine SDK. fabengine will attempt to find this
     automatically by looking for dev_appserver.py on your `PATH`. (Optional)
   - `dev_appserver`: The path to `dev_appserver.py`. fabengine will use 
     `<gae_path>/dev_appserver.py` if it is not provided. (Optional)
   - `appcfg`: The path to `appcfg.py`. fabengine will use `<gae_path>/appcfg.py` if it not
     provided. (Optional)

 4. Use fabric!

        fab -l

Commands
--------

 * **bundle_packages** - Creates zipimport compatible archives from your `requirements.txt` file
   into the folder `packages`. See `help(fabengine.BundlePackages)` for a loader.

 * **dev_appserver** - Runs `dev_appserver.py`

 * **show_config** - Shows the internal fabengine config.

 * **test** - Runs `nosetests`

 * **fix_virtualenv_paths** - Applies some permanent path manipulation to the current virtualenv
   to fix loading of libraries bundled with the appengine sdk.

 * **update**, **update_indexes**, **update_queues**, **vacuum_indexes**, **update_dos**, 
   **update_cron** - Aliases for appcfg.py commands. Arguments passed in are forwarded to appcfg.py.
   e.g.:

        fab fabengine.update:version=FOO,R --> appcfg.py update --version=FOO -R

TODO
----

 * Add missing appcfg.py commands.
 * Copy LICENSE, README, etc from package-source into bundled packages.

