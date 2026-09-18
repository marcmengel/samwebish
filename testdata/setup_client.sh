spack load --first sam-web-client@3.6
spack load --first ifdhc@2.8.0
export SAM_WEB_BASE_URL=https://localhost:4883/api
export IFDH_BASE_URI=https://localhost:4883/api
export SAM_EXPERIMENT=hypot
htgettoken -i hypot -a htvaultprod.fnal.gov > /dev/null 2>&1
