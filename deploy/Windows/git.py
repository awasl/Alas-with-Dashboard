import configparser
import os

from deploy.Windows.config import DeployConfig
from deploy.Windows.logger import Progress, logger
from deploy.Windows.utils import cached_property
from deploy.git_over_cdn.client import GitOverCdnClient


class GitConfigParser(configparser.ConfigParser):
    def check(self, section, option, value):
        result = self.get(section, option, fallback=None)
        if result == value:
            logger.info(f'Git config {section}.{option} = {value}')
            return True
        else:
            return False


class GitOverCdnClientWindows(GitOverCdnClient):
    def update(self, *args, **kwargs):
        Progress.GitInit()
        _ = super().update(*args, **kwargs)
        Progress.GitShowVersion()
        return _

    @cached_property
    def latest_commit(self) -> str:
        _ = super().latest_commit
        Progress.GitLatestCommit()
        return _

    def download_pack(self):
        _ = super().download_pack()
        Progress.GitDownloadPack()
        return _


class GitManager(DeployConfig):
    @staticmethod
    def remove(file):
        try:
            os.remove(file)
            logger.info(f'Removed file: {file}')
        except FileNotFoundError:
            logger.info(f'File not found: {file}')

    @cached_property
    def git_config(self):
        conf = GitConfigParser()
        conf.read('./.git/config')
        return conf

    def git_repository_init(
            self, repo, source='origin', branch='master', proxy='', ssl_verify=True
    ):
        logger.hr('Git Init', 1)
        if not self.execute(f'"{self.git}" init', allow_failure=True):
            self.remove('./.git/config')
            self.remove('./.git/index')
            self.remove('./.git/HEAD')
            self.remove('./.git/ORIG_HEAD')
            self.execute(f'"{self.git}" init')
        Progress.GitInit()

        logger.hr('Set Git Proxy', 1)
        if proxy:
            if not self.git_config.check('http', 'proxy', value=proxy):
                self.execute(f'"{self.git}" config --local http.proxy {proxy}')
            if not self.git_config.check('https', 'proxy', value=proxy):
                self.execute(f'"{self.git}" config --local https.proxy {proxy}')
        else:
            if not self.git_config.check('http', 'proxy', value=None):
                self.execute(f'"{self.git}" config --local --unset http.proxy', allow_failure=True)
            if not self.git_config.check('https', 'proxy', value=None):
                self.execute(f'"{self.git}" config --local --unset https.proxy', allow_failure=True)

        if ssl_verify:
            if not self.git_config.check('http', 'sslVerify', value='true'):
                self.execute(f'"{self.git}" config --local http.sslVerify true', allow_failure=True)
        else:
            if not self.git_config.check('http', 'sslVerify', value='false'):
                self.execute(f'"{self.git}" config --local http.sslVerify false', allow_failure=True)
        Progress.GitSetConfig()

        logger.hr('Set Git Repository', 1)
        if not self.git_config.check(f'remote "{source}"', 'url', value=repo):
            if not self.execute(f'"{self.git}" remote set-url {source} {repo}', allow_failure=True):
                self.execute(f'"{self.git}" remote add {source} {repo}')
        Progress.GitSetRepo()

        logger.hr('Fetch Repository Branch', 1)
        self.execute(f'"{self.git}" fetch {source} {branch}')
        Progress.GitFetch()

        logger.hr('Fast-forward Repository Branch', 1)
        # Remove git lock
        for lock_file in [
            './.git/index.lock',
            './.git/HEAD.lock',
            './.git/refs/heads/master.lock',
        ]:
            if os.path.exists(lock_file):
                logger.info(f'Lock file {lock_file} exists, removing')
                os.remove(lock_file)

        remote_branch = f'{source}/{branch}'
        if self.execute(f'"{self.git}" rev-parse --verify HEAD', allow_failure=True):
            # Never discard local changes or commits during an automatic update.
            self.execute(f'"{self.git}" diff --quiet')
            self.execute(f'"{self.git}" diff --cached --quiet')
            self.execute(f'"{self.git}" checkout {branch}')
            self.execute(f'"{self.git}" merge-base --is-ancestor HEAD {remote_branch}')
            self.execute(f'"{self.git}" merge --ff-only {remote_branch}')
        else:
            # A freshly initialized repository has no HEAD yet.
            self.execute(f'"{self.git}" checkout -B {branch} {remote_branch}')
        Progress.GitReset()
        Progress.GitCheckout()

        logger.hr('Show Version', 1)
        self.execute(f'"{self.git}" --no-pager log --no-merges -1')
        Progress.GitShowVersion()

    @property
    def goc_client(self):
        client = GitOverCdnClient(
            url='https://vip.123pan.cn/1815343254/pack/LmeSzinc_StarRailCopilot_master',
            folder=self.root_filepath,
            source='origin',
            branch='master',
            git=self.git,
        )
        client.logger = logger
        return client

    def git_install(self):
        logger.hr('Update Alas', 0)

        if not self.AutoUpdate:
            logger.info('AutoUpdate is disabled, skip')
            Progress.GitShowVersion()
            return

        if self.GitOverCdn:
            if self.goc_client.update():
                return

        self.git_repository_init(
            repo=self.Repository,
            source='origin',
            branch=self.Branch,
            proxy=self.GitProxy,
            ssl_verify=self.SSLVerify,
        )
