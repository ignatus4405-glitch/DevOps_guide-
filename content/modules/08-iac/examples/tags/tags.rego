package main

deny contains msg if {
  resource := input.resource_changes[_]
  after := resource.change.after
  is_object(after)
  tags := object.get(after, "tags", {})
  is_object(tags)
  owner := object.get(tags, "owner", "")
  owner == ""
  msg := sprintf("ресурс %s без owner", [resource.address])
}
