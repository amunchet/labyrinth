// authService.js

import auth0 from 'auth0-js'
import EventEmitter from 'events'
import authConfig from '../auth_config.json'

const webAuth = new auth0.WebAuth({
    domain: authConfig.domain,
    redirectUri: `${window.location.origin}/callback`,
    clientID: authConfig.clientId,
    audience: authConfig.audience, // add the audience
    responseType: 'token id_token', // request 'token' as well as 'id_token'
    scope: 'openid profile email',
})

const localStorageKey = 'loggedIn'
const loginEvent = 'loginEvent'

class AuthService extends EventEmitter {
    idToken = null
    profile = null
    tokenExpiry = null

    // Add fields here to store the Access Token and the expiry time
    accessToken = null
    accessTokenExpiry = null

    // Starts the user login flow
    login(customState) {
        webAuth.authorize({
            appState: customState,
        })
    }

    // Handles the callback request from Auth0
    handleAuthentication() {
        return new Promise((resolve, reject) => {
            //Check for locally stored authentication
            if (this.isAuthenticated()) {
                this.idToken = localStorage.getItem('idToken')
                this.profile = JSON.parse(localStorage.getItem('profile'))
                this.tokenExpiry = localStorage.getItem('tokenExpiry')
                this.accessToken = localStorage.getItem('accessToken')
                this.accessTokenExpiry = localStorage.getItem('accessExpiry')

                this.emit(loginEvent, {
                    loggedIn: true,
                    profile: this.profile,
                    //state: authResult.appState,
                })
                resolve(this.idToken)
            } else {
                webAuth.parseHash((err, authResult) => {
                    if (err) {
                        reject(err)
                    } else {
                        this.localLogin(authResult)
                        resolve(authResult.idToken)
                    }
                })
            }
        })
    }

    localLogin(authResult) {
        this.idToken = authResult.idToken
        this.profile = authResult.idTokenPayload

        // Convert the JWT expiry time from seconds to milliseconds
        this.tokenExpiry = new Date(this.profile.exp * 1000)

        // NEW - Save the Access Token and expiry time in memory
        this.accessToken = authResult.accessToken

        // Convert expiresIn to milliseconds and add the current time
        // (expiresIn is a relative timestamp, but an absolute time is desired)
        this.accessTokenExpiry = new Date(
            Date.now() + authResult.expiresIn * 1000
        )

        localStorage.setItem(localStorageKey, 'true')
        localStorage.setItem('idToken', this.idToken)
        localStorage.setItem('accessToken', this.accessToken)
        localStorage.setItem('profile', JSON.stringify(this.profile))
        localStorage.setItem('tokenExpiry', this.tokenExpiry)
        localStorage.setItem('accessExpiry', this.accessTokenExpiry)

        this.emit(loginEvent, {
            loggedIn: true,
            profile: authResult.idTokenPayload,
            state: authResult.appState,
        })
    }

    renewTokens() {
        return new Promise((resolve, reject) => {
            if (localStorage.getItem(localStorageKey) !== 'true') {
                return reject('Error: Not logged in')
            }
            if (this.isAuthenticated()) {
                resolve(localStorage)
            } else {
                webAuth.checkSession({}, (err, authResult) => {
                    if (err) {
                        reject(err)
                    } else {
                        this.localLogin(authResult)
                        resolve(authResult)
                    }
                })
            }
        })
    }

    logOut() {
        localStorage.removeItem(localStorageKey)
        localStorage.removeItem('idToken')
        localStorage.removeItem('profile')
        localStorage.removeItem('tokenExpiry')
        localStorage.removeItem('accessExpiry')
        localStorage.removeItem('accessToken')

        this.idToken = null
        this.tokenExpiry = null
        this.profile = null
        this.accessToken = null
        this.accessTokenExpiry = null

        webAuth.logout({
            returnTo: window.location.origin,
        })

        this.emit(loginEvent, {
            loggedIn: false,
        })
    }

    isAuthenticated() {
        this.idToken = localStorage.getItem('idToken')
        this.profile = JSON.parse(localStorage.getItem('profile'))
        this.tokenExpiry = new Date(localStorage.getItem('tokenExpiry'))
        this.accessTokenExpiry = new Date(localStorage.getItem('accessExpiry'))
        this.accessToken = localStorage.getItem('accessToken')
        

        var retval = Date.now() < this.tokenExpiry && localStorage.getItem(localStorageKey) === 'true'
        return retval
    }
    isAccessTokenValid() {
        return (
            this.accessToken &&
            this.accessTokenExpiry &&
            Date.now() < this.accessTokenExpiry
        )
    }

    getAccessToken() {
        return new Promise((resolve, reject) => {
            if (this.isAccessTokenValid()) {
                resolve(this.accessToken)
            } else {
                this.renewTokens().then(authResult => {
                    resolve(authResult.accessToken)
                }, reject)
            }
        })
    }
}

export default new AuthService()
