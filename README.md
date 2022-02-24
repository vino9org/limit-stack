## Vino Bank Demo: Limits Management Module

Stack:
  AWS Lambda
  DynamoDB
  AWS CDK


### API Spec
```
=======
request
=======
POST /limit?customer_id=<cust_id>
POST /customer/<cust_id>/limit

code: 201. 
body: {"req_id" : "<req_id>"}

=======
release
=======
DELETE /limit/<req_id>

code: 200
body: {"amount" : <amount>}


=======
confirm
=======
POST /limit/<req_id>/confirm

code: 200
body: {"amount" : <amount>}


```

## Notes

Pros:
* infra and code in one repo

Cons:
* PythonFunction buggy. workaround is to use separate layer to dependencies (extra repo to maintain) or inline the dependencies in runtime directory (extra steps, flake8 throws bunch of warnings)


### TODO
1. use unique event bridge to avoid event trigger lambda in multiple stacks
2. externalize runtime dependencies into its own layer