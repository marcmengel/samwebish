
start_server() {
    (
      . ./setup.sh
      python samwebish.py > server.out 2>&1 &
      echo $! > server.pid
    )

    sleep 1
    if kill -0 $(<server.pid)
    then
        succeeded "python samwebish.py &"
    else
        failed "python samwebish.py &" 
        exit
    fi
    trap "kill $(<server.pid); rm server.pid" 0 1 2 3 4 5 6 7 8
    sleep 1
    # let server wake up...
}

. ./setup_client.sh

verbose_check() {
   if [ "$1" = "-v" ] 
   then 
      verbose=true
   else
      verbose=false
   fi
}
succeeded() {
   if $verbose
   then
       echo "Succeeded: $*"
   else
       printf "."
   fi
}

failed() {
   if $verbose
   then
       echo "Failed: $*"
   else
       printf "F"
   fi
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

verbose_check "$@"
start_server
run_expecting "samweb locate-file a.fcl" "FNAL_DCACHE_DISK_TEST" "/pnfs/fnal.gov/" "a.fcl"
run_expecting "samweb list-definitions" "tst_q_1710507530" "tst_q_1710508175"
run_expecting "samweb describe-definition tst_q_1710508175" "Definition Name: tst_q_1710508175" "Dimensions: files from mengel:tst1710508175"
run_expecting "samweb count-definition-files tst_q_1710508175" "4"
run_expecting "samweb list-definition-files --summary tst_q_1788293412.8690157" "File count:" "25" "Total size:" "906"
run_expecting "samweb list-files defname:gen_cfg" "c.fcl" "d.fcl"

echo



