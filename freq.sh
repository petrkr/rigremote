
if [[ ! -z "$1" ]]
then
  cmd="F $1"
else
  cmd="f"
fi

rigctl -m 2 $cmd
