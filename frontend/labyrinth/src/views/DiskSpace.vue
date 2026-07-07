<template>
  <b-container fluid class="mt-4">
    <b-card no-body>
      <b-tabs card pills>
        <!-- Disk Space Tab -->
        <b-tab title="Disk Space Check" lazy class="mt-0 pt-0 pb-0 mb-0">
          <DiskSpaceView />
        </b-tab>

        <!-- Settings Tab -->
        <b-tab title="Settings" lazy>
          <DiskSpaceSettings />
        </b-tab>
      </b-tabs>
    </b-card>
  </b-container>
</template>

<script>
import DiskSpaceView from "@/components/DiskSpace/DiskSpaceView";
import DiskSpaceSettings from "@/components/DiskSpace/DiskSpaceSettings";

export default {
  name: "DiskSpace",
  components: {
    DiskSpaceView,
    DiskSpaceSettings,
  },
};
</script>

<style lang="scss" scoped>
</style>
