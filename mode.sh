
if [[ ! -z "$1" ]]
then
  cmd="M $1 $2"
else
  cmd="m"
fi

rigctl -m 2 $cmd
