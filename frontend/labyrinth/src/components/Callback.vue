<!-- src/components/Callback.vue -->

<template>
    <div>
    </div>
</template>

<script>
export default {
    methods: {
        handleLoginEvent() {
            //console.log(data);
            /* istanbul ignore next */
            this.$router.push('/')
            window.location.href = window.location.href + "?callback=1&date=" + Date.now()
        },
    },
    created: async function() {
        try {
            await this.$auth.handleAuthentication()
        } catch (e) {
            console.log(e)
        }
    },
    mounted() {},
}
</script>