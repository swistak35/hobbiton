# Hobbiton Configuration

## Git repository on server

```
git init
git config receive.denyCurrentBranch updateInstead
```

## Pihole

```
# https://github.com/pi-hole/docker-pi-hole#installing-on-ubuntu-or-fedora
sudo sed -r -i.orig 's/#?DNSStubListener=yes/DNSStubListener=no/g' /etc/systemd/resolved.conf
sudo sh -c 'rm /etc/resolv.conf && ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf'
systemctl restart systemd-resolved

sudo docker-compose up -d
```
