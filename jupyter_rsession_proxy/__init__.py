import os
import tempfile
import subprocess
import getpass
import shutil
from textwrap import dedent


def get_r_env():
    env = {}
    executable = 'R'
    try:
        # get notebook app
        from notebook.notebookapp import NotebookApp
        nbapp = NotebookApp.instance()
        kernel_name = nbapp.kernel_manager.default_kernel_name
        if kernel_name:
            kernel_spec = nbapp.kernel_spec_manager.get_kernel_spec(kernel_name)
            env.update(kernel_spec.env)
            executable = kernel_spec.argv[0]

            # patch LD_LIBRARY_PATH for conda env
            conda_lib_dir = os.path.join(env['CONDA_PREFIX'], 'lib')
            #r_lib_dir = os.path.join(conda_lib_dir, 'R/lib')
            env.update({
                # 'LD_LIBRARY_PATH': r_lib_dir + ':' + conda_lib_dir
                'LD_LIBRARY_PATH': conda_lib_dir
            })
    except Exception:
        nbapp.log.warning('Error when trying to get R executable from kernel')

    # Detect various environment variables rsession requires to run
    # Via rstudio's src/cpp/core/r_util/REnvironmentPosix.cpp
    cmd = [executable, '--slave', '--vanilla', '-e',
           'cat(paste(R.home("home"),R.home("share"),R.home("include"),R.home("doc"),getRversion(),sep=":"))']
    r_output = subprocess.check_output(cmd)
    R_HOME, R_SHARE_DIR, R_INCLUDE_DIR, R_DOC_DIR, version = \
        r_output.decode().split(':')
    # TODO:
    #   maybe set a few more env vars?
    #   e.g. MAXENT, DISPLAY='' (to avoid issues with java)
    #   e.g. would be nice if RStudio terminal starts with correct conda env?
    #   -> either patch ~/Renviron / Renviron.site
    #   -> user Rprofile.site (if conda env specific?)
    #   -> use ~/.Rprofile ... if user specific?
    #   make R kernel used configurable?
    #     ... or rather use standard system R installation, and let user install stuff in home folder?
    env.update({
        'R_DOC_DIR': R_DOC_DIR,
        'R_HOME': R_HOME,
        'R_INCLUDE_DIR': R_INCLUDE_DIR,
        'R_SHARE_DIR': R_SHARE_DIR,
        'RSTUDIO_DEFAULT_R_VERSION_HOME': R_HOME,
        'RSTUDIO_DEFAULT_R_VERSION': version,
    })
    return env


def setup_shiny():
    '''Manage a Shiny instance.'''

    def _get_shiny_cmd(port):
        # server.r_path ???
        conf = dedent("""
            run_as {user};
            server {{
                bookmark_state_dir {site_dir}/shiny-server-boomarks;
                listen {port};
                location / {{
                    site_dir {site_dir};
                    log_dir {site_dir}/logs;
                    directory_index on;
                }}
            }}
        """).format(
            user=getpass.getuser(),
            port=str(port),
            site_dir=os.getcwd()
        )

        f = tempfile.NamedTemporaryFile(mode='w', delete=False)
        f.write(conf)
        f.close()
        return ['shiny-server', f.name]

    def _get_shiny_env(port):
        env = get_r_env()
        return env

    return {
        'command': _get_shiny_cmd,
        'environment': _get_shiny_env,
        'launcher_entry': {
            'title': 'Shiny',
            'icon_path': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons', 'shiny.svg')
        }
    }


def setup_rstudio():

    def _get_rsession_env(port):
        env = get_r_env()

        # rserver needs USER to be set to something sensible,
        # otherwise it'll throw up an authentication page
        if not os.environ.get('USER', ''):
            env['USER'] = getpass.getuser()

        return env

    def _get_r_executable():
        try:
            # get notebook app
            from notebook.notebookapp import NotebookApp
            nbapp = NotebookApp.instance()
            # get R executable:
            kernel_name = nbapp.kernel_manager.default_kernel_name
            if kernel_name:
                kernel_spec = nbapp.kernel_spec_manager.get_kernel_spec(kernel_name)
                return kernel_spec.argv[0]
        except Exception:
            nbapp.log.warning('Error when trying to get R executable from kernel')
        return 'R'

    def _get_rsession_cmd(port):
        # Other paths rsession maybe in
        other_paths = [
            # When rstudio-server deb is installed
            '/usr/lib/rstudio-server/bin/rserver',
        ]
        if shutil.which('rserver'):
            executable = 'rserver'
        else:
            for op in other_paths:
                if os.path.exists(op):
                    executable = op
                    break
            else:
                raise FileNotFoundError('Can not find rserver in PATH')

        cmd = [
            executable,
            '--www-port=' + str(port),
            '--rsession-which-r=' + _get_r_executable(),
        ]
        env = get_r_env()
        if env.get('LD_LIBRARY_PATH'):
            cmd.append('--rsession-ld-library-path=' + env['LD_LIBRARY_PATH'])
        return cmd

    return {
        'command': _get_rsession_cmd,
        'environment': _get_rsession_env,
        'launcher_entry': {
            'title': 'RStudio',
            'icon_path': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons', 'rstudio.svg')
        }
    }
