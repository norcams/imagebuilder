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
pip install --upgrade setuptools
python setup.py develop
pip install -r requirements.txt
```
