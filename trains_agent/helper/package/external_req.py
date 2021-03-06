from collections import OrderedDict
from typing import Text

from .base import PackageManager
from .requirements import SimpleSubstitution
from ..base import safe_furl as furl


class ExternalRequirements(SimpleSubstitution):

    name = "external_link"

    def __init__(self, *args, **kwargs):
        super(ExternalRequirements, self).__init__(*args, **kwargs)
        self.post_install_req = []
        self.post_install_req_lookup = OrderedDict()

    def match(self, req):
        # match both editable or code or unparsed
        if not (not req.name or req.req and (req.req.editable or req.req.vcs)):
            return False
        if not req.req or not req.req.line or not req.req.line.strip() or req.req.line.strip().startswith('#'):
            return False
        return True

    def post_install(self, session):
        post_install_req = self.post_install_req
        self.post_install_req = []
        for req in post_install_req:
            try:
                freeze_base = PackageManager.out_of_scope_freeze() or ''
            except:
                freeze_base = ''

            req_line = req.tostr(markers=False)
            if req.req.vcs and req_line.startswith('git+'):
                try:
                    url_no_frag = furl(req_line)
                    url_no_frag.set(fragment=None)
                    # reverse replace
                    fragment = req_line[::-1].replace(url_no_frag.url[::-1], '', 1)[::-1]
                    vcs_url = req_line[4:]
                    # reverse replace
                    vcs_url = vcs_url[::-1].replace(fragment[::-1], '', 1)[::-1]
                    from ..repo import Git
                    vcs = Git(session=session, url=vcs_url, location=None, revision=None)
                    vcs._set_ssh_url()
                    new_req_line = 'git+{}{}'.format(vcs.url_with_auth, fragment)
                    if new_req_line != req_line:
                        url_pass = furl(new_req_line).password
                        print('Replacing original pip vcs \'{}\' with \'{}\''.format(
                            req_line, new_req_line.replace(url_pass, '****', 1) if url_pass else new_req_line))
                        req_line = new_req_line
                except Exception:
                    print('WARNING: Failed parsing pip git install, using original line {}'.format(req_line))

            PackageManager.out_of_scope_install_package(req_line, "--no-deps")
            try:
                freeze_post = PackageManager.out_of_scope_freeze() or ''
                package_name = list(set(freeze_post['pip']) - set(freeze_base['pip']))
                if package_name and package_name[0] not in self.post_install_req_lookup:
                    self.post_install_req_lookup[package_name[0]] = req.req.line
            except:
                pass
            if not PackageManager.out_of_scope_install_package(req_line, "--ignore-installed"):
                raise ValueError("Failed installing GIT/HTTPs package \'{}\'".format(req_line))

    def replace(self, req):
        """
        Replace a requirement
        :raises: ValueError if version is pre-release
        """
        # Store in post req install, and return nothing
        self.post_install_req.append(req)
        # mark skip package, we will install it in post install hook
        return Text('')

    def replace_back(self, list_of_requirements):
        if 'pip' in list_of_requirements:
            original_requirements = list_of_requirements['pip']
            list_of_requirements['pip'] = [r for r in original_requirements
                                           if r not in self.post_install_req_lookup]
            list_of_requirements['pip'] += [self.post_install_req_lookup.get(r, '')
                                            for r in self.post_install_req_lookup.keys() if r in original_requirements]
        return list_of_requirements
