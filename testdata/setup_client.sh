. $SPACK_ROOT/setup-env.sh
spack env activate samwebish

export SAM_WEB_BASE_URL=https://localhost:9443/api
export IFDH_BASE_URI=https://localhost:9443/api
export SAM_EXPERIMENT=hypot

htgettoken 
