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
