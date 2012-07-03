#!/bin/bash
#set -x
function prepare_mangrove_env {
	cd ../mangrove && \
	pip install -r requirements.pip && \
	python setup.py develop && \
	cd ../datawinners
}

function prepare_datawinner_env {
	pip install -r requirements.pip && \
	cp datawinners/local_settings_example.py datawinners/local_settings.py
}

function migrate_db {
	python datawinners/manage.py migrate
}

function pre_commit {
    update_source && \
	prepare_mangrove_env && \
	prepare_datawinner_env && \
	restore_database && \
	cd .. & \
	unit_test && \
	function_test
}

function unit_test {
	echo "running unit test" && \
	cd datawinners && \
	python manage.py recreatedb && \
	python manage.py test &&\
	cd ..
}

function function_test {
	echo "running function test" && \
	cp datawinners/local_settings_example.py func_tests/resources/local_settings.py && \
	restore_database && \
	python manage.py recreatedb && \
	cd ../func_tests && \
	nosetests && \
	killall -9 chromedriver
}

function restore_database {
	echo "recreating database" && \
	dropdb geodjango && \
	createdb -T template_postgis geodjango && \
	cd datawinners && \
	python manage.py syncdb --noinput && \
	python manage.py migrate && \
	python manage.py loadshapes
}

function show_help {
	echo "Usage: build.sh [COMMAND]"
	echo "COMMAND"
	echo "pc: \tthis will run all the unit test and function test"
	echo "ut: \tthis will run all the unit test"
	echo "ft: \tthis will run all the function test"
	echo "rd: \tdestory and recreate database"
	echo "us: \tupdate source codes of mangrove and datawinners"
}

function update_source {
    echo "Update source code ...."
    cd ../mangrove && \
    git pull --rebase && \
    cd ../datawinners && \
    git pull --rebase
}

function main {
	case $1 in
		pc) pre_commit;;
		ut) unit_test;;
		ft) function_test;;
		rd) restore_database;;
		us) update_source;;
		*) show_help && exit 1;;
	esac
}

main $@
