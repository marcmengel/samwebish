
start_server() {
    (
      . ./setup.sh
      python samwebish.py > server.out 2>&1 &
      echo $! > server.pid
    )

    trap "kill $(<server.pid); rm server.pid" 0 1 2 3 4 5 6 7 8
}

. ./setup_client.sh

succeeded() {
   echo "Succeeded: $*"
}

failed() {
   echo "Failed: $*"
}
run_expecting()  {

   cmd=$1
   shift
   fc=0
   out=$($cmd)
   for pat in "$@"
   do
       if echo "$out" | grep "$pat" > /dev/null 
       then 
           :
       else
           failed "$cmd $pat"
           fc=$((fc + 1))
       fi
   done
   if [ "$fc" == "0" ]
   then 
       succeeded "$cmd"
   fi
}

start_server
run_expecting "samweb locate-file a.fcl" "FNAL_DCACHE_DISK_TEST" "/pnfs/fnal.gov/" "a.fcl"
run_expecting "samweb list-definitions" "tst_q_1710507530" "tst_q_1710508175"
run_expecting "samweb describe-definition tst_q_1710508175" "Definition Name: tst_q_1710508175" "Dimensions: files from mengel:tst1710508175"


