<template>
  <b-container fluid class="mt-4">
    <b-card no-body>
      <b-tabs card pills>
        <b-tab title="EC2 Instances" lazy class="mt-0 pt-0 pb-0 mb-0">
          <AwsInstancesView />
        </b-tab>
        <b-tab title="Settings" lazy>
          <AwsSettings />
        </b-tab>
        <b-tab title="Documentation" lazy>
          <AwsDocumentation />
        </b-tab>
      </b-tabs>
    </b-card>
  </b-container>
</template>

<script>
import AwsInstancesView from "@/components/AWS/AwsInstancesView";
import AwsSettings from "@/components/AWS/AwsSettings";
import AwsDocumentation from "@/components/AWS/AwsDocumentation";

export default {
  name: "AWS",
  components: {
    AwsInstancesView,
    AwsSettings,
    AwsDocumentation,
  },
};
</script>
