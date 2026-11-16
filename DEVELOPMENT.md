## NREC development on a builder node

``` bash
yum install -y python-virtualenv
cd /opt
mv imagebuilder/ rpm.imagebuilder/
git clone https://github.com/norcams/imagebuilder
cd imagebuilder
virtualenv . -p /usr/bin/python3
source bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

`pip install -e .` replaces the old `python setup.py develop`, which setuptools
has deprecated. Package metadata and the console script live in
`pyproject.toml`; there is no `setup.py` any more.

## Tests

``` bash
pip install pytest
pytest
```

They use stand-in OpenStack clients and a fake HTTP layer, so nothing reaches a
cloud or the network and no credentials are needed. CI runs them on every push.

## Python version

`requirements.txt` pins for Python 3.9, the stock interpreter on EL9. Red Hat
maintains 3.9 for the full RHEL 9 life cycle, so it stays patched well past its
upstream end of life, but two pins are capped by it: keystoneauth1 and
openstacksdk.

That floor is fine for OpenStack 2025.1, where 3.9 is the minimum supported
runtime. 2025.2 raised the minimum to 3.10, and while its constraints still
carry 3.9 fallbacks pinning exactly the versions used here, those fallbacks
will not last forever.

Moving off 3.9 does not require EL10. Newer interpreters ship on EL9 as
parallel-installable AppStream packages, alongside the stock 3.9 and with their
own pip and site-packages:

``` bash
dnf install -y python3.12
python3.12 -m venv .
source bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

When switching, uncomment the 3.11+ block at the bottom of `requirements.txt`
and comment out the three capped pins above it. Nothing in the code needs
changing; it has been checked on interpreters up to 3.14.
