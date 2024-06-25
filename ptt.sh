
if [[ ! -z "$1" ]]
then
  cmd="T $1"
else
  cmd="t"
fi

rigctl -m 2 $cmd
