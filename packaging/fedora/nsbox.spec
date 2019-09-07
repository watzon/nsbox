%global goipath github.com/refi64/nsbox

%define reldir() %{lua:\
  local arg = rpm.expand('%1')\
  local prefix = rpm.expand('%{_prefix}')\
  assert(arg:sub(1, prefix:len()) == prefix, "arg " .. arg .. " does not start with " .. prefix)\
  local result = arg:sub(prefix:len() + 1):gsub('^/', '')\
  print(result)}

%global relbindir %{reldir %{_bindir}}
%global rellibexecdir %{reldir %{_libexecdir}}
%global reldatadir %{reldir %{_datadir}}

# nsbox-host has missing build-ids due to being static.
%global _missing_build_ids_terminate_build 0

Name: @PRODUCT_NAME
Version: @VERSION
Release: 1%{?dist}
Summary: A multi-purpose, nspawn-powered container manager
License: MPL-2.0
URL: https://nsbox.dev/
BuildRequires: gcc
BuildRequires: gcc-c++
BuildRequires: golang
BuildRequires: python3
%if 0%{?fedora} >= 31
BuildRequires: go-rpm-macros
%endif
BuildRequires: ninja-build
Source0: nsbox-sources.tar
Source1: https://gn.googlesource.com/gn/+archive/@GN.tar.gz#/gn.tar.gz
@SPECDEFS

%description
nsbox is a multi-purpose, nspawn-powered container manager.

%if "%{name}" == "nsbox-edge"
%package alias
Summary: Alias for nsbox-edge
%description alias
Installs the nsbox alias for nsbox-edge.
%endif

%prep
rm -rf %{name}-%{version}

# Order of these commands is important!
%setup_go_archives_universal
%{?setup_go_archives_pre_f31_only}

%setup -q -c -T -n %{name}-%{version}/gn -a 1
%setup -q -c -D

%setup_go_repo_links

# @@ is here for substitute_file.py.
cat >build/go-shim.sh <<'EOF'
#!/bin/sh
if [[ "$1" == "build" ]]; then
  shift
  # XXX: We can't use buildmode=pie for our static nsbox-host, so remove it here.
  extra_args=""
  [[ "$CGO_ENABLED" == "0" ]] && extra_args="-buildmode=exe" ||:
  %gobuild $extra_args "$@@"
else
  go "$@@"
fi
EOF

chmod +x build/go-shim.sh

%build
cd gn
# last_commit_position.h generation wants Git, so write it manually.
python3 build/gen.py --no-last-commit-position --no-static-libstdc++
# XXX: this sort-of works, it's good enough for our purposes.
echo -e '#pragma once\n#define LAST_COMMIT_POSITION "@GN"' > out/last_commit_position.h
ninja -C out
cd ..

mkdir -p out
cat >out/args.gn <<EOF
go_exe = "$PWD/build/go-shim.sh"
bin_dir = "%{relbindir}"
libexec_dir = "%{rellibexecdir}"
share_dir = "%{reldatadir}"
state_dir = "%{_sharedstatedir}"
config_dir = "%{_sysconfdir}"
override_release_version = "@VERSION"
%if "%{name}" != "nsbox-edge"
is_stable_build = true
%endif
EOF
gn/out/gn gen out
ninja -C out

%install
mkdir -p %{buildroot}/%{_prefix}
cp -r out/install/%{_sysconfdir} %{buildroot}
cp -r out/install/{%{relbindir},%{rellibexecdir},%{reldatadir}} %{buildroot}/%{_prefix}
chmod -R g-w %{buildroot}

%files
%{_bindir}/%{name}
%{_sysconfdir}/profile.d/%{name}.sh
%{_libexecdir}/%{name}/nsbox-host
%{_libexecdir}/%{name}/nsboxd
%{_datadir}/%{name}/data/getty-override.conf
%{_datadir}/%{name}/data/nsbox-container.target
%{_datadir}/%{name}/data/nsbox-init.service
%{_datadir}/%{name}/data/scripts/nsbox-apply-env.sh
%{_datadir}/%{name}/data/scripts/nsbox-enter-run.sh
%{_datadir}/%{name}/data/scripts/nsbox-enter-setup.sh
%{_datadir}/%{name}/data/scripts/nsbox-init.sh
%{_datadir}/%{name}/release/VERSION
%{_datadir}/%{name}/release/BRANCH

%if "%{name}" == "nsbox-edge"
%files alias
%{_bindir}/nsbox
%endif
