#!/bin/sh

# DO NOT RUN THIS FILE IF YOU DON'T KNOW WHAT YOU ARE DOING!

promptyn () {
    while true; do
        read -p "$1 " yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

deploy () {
    echo "DEPLOYING...";
    fab -H keywords.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords2.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords3.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords4.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords5.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &

    fab -H keywords6.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords7.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords8.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords9.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords10.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords11.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &

    fab -H keywords12.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords13.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords14.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords15.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords16.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords17-pg.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &

    fab -H keywords18.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords19.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords20.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords22.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords23.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &

    fab -H keywords24.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &

    fab -H keywords25.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords26-maplin.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords27-maplin.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords28-maplin.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
    fab -H keywords29-pg.contentanalyticsinc.com set_production deploy:branch=sc_production,restart_scrapyd=True -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &

    fab -H sc-tests.contentanalyticsinc.com set_production deploy_sc_test_server:branch=sc_production -u ubuntu -i ../../../ssh_certificates//ubuntu_id_rsa &
}

if promptyn "Do you really want to deploy the code to all the servers?"; then
    deploy;
else
    echo "abort";
    exit;
fi