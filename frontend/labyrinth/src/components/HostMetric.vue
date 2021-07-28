<template>
    <b-modal id="service_detail">
        {{data}}
    </b-modal>


</template>
<script>
export default {
  name: "HostMetric",
  props: ["data"]
}
</script>